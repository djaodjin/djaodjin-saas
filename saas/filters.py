# Copyright (c) 2019, DjaoDjin inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
from __future__ import unicode_literals

import logging, operator
from functools import reduce

from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.utils import six
from django.utils.encoding import force_text
from rest_framework.compat import coreapi, coreschema
from rest_framework.filters import (OrderingFilter as BaseOrderingFilter,
    SearchFilter as BaseSearchFilter)
from rest_framework.compat import distinct

from . import settings

LOGGER = logging.getLogger(__name__)


class SearchFilter(BaseSearchFilter):

    search_field_param = settings.SEARCH_FIELDS_PARAM

    def get_query_fields(self, request):
        return request.query_params.getlist(self.search_field_param)

    def filter_valid_fields(self, model_fields, fields, view):
        # We add all the fields that could be aliases then filter out the ones
        # which are not present in the model.
        alternate_fields = getattr(view, 'alternate_fields', {})
        for field in fields:
            alternate_field = alternate_fields.get(field, None)
            if alternate_field:
                if isinstance(alternate_field, (list, tuple)):
                    fields += tuple(alternate_field)
                else:
                    fields += tuple([alternate_field])
        return tuple([field for field in fields if field in model_fields])

    def get_valid_fields(self, queryset, view, context={}):
        model_fields = set([
            field.name for field in queryset.model._meta.get_fields()])
        fields = self.get_query_fields(view.request)
        # client-supplied fields take precedence
        if fields:
            fields = self.filter_valid_fields(model_fields, fields, view)
        # if there are no fields (due to empty query params or wrong
        # fields we fallback to fields specified in the view
        if not fields:
            fields = getattr(view, 'search_fields', [])
            fields = self.filter_valid_fields(model_fields, fields, view)
        return fields

    def filter_queryset(self, request, queryset, view):
        search_fields = self.get_valid_fields(queryset, view)
        search_terms = self.get_search_terms(request)
        LOGGER.debug("[SearchFilter] search_terms=%s, search_fields=%s",
            search_terms, search_fields)

        if not search_fields or not search_terms:
            return queryset

        orm_lookups = [
            self.construct_search(six.text_type(search_field))
            for search_field in search_fields
        ]

        base = queryset
        conditions = []
        for search_term in search_terms:
            queries = [
                models.Q(**{orm_lookup: search_term})
                for orm_lookup in orm_lookups
            ]
            conditions.append(reduce(operator.or_, queries))
        queryset = queryset.filter(reduce(operator.and_, conditions))

        if self.must_call_distinct(queryset, search_fields):
            # Filtering against a many-to-many field requires us to
            # call queryset.distinct() in order to avoid duplicate items
            # in the resulting queryset.
            # We try to avoid this if possible, for performance reasons.
            queryset = distinct(queryset, base)
        return queryset


class OrderingFilter(BaseOrderingFilter):

    def get_valid_fields(self, queryset, view, context={}):
        model_fields = set([
            field.name for field in queryset.model._meta.get_fields()])
        # XXX base
        base_fields = super(OrderingFilter, self).get_valid_fields(
            queryset, view, context=context)
        alternate_fields = getattr(view, 'alternate_fields', {})
        for field in base_fields:
            alternate_field = alternate_fields.get(field[0], None)
            if alternate_field:
                if isinstance(alternate_field, (list, tuple)):
                    base_fields += [(item, item) for item in alternate_field]
                else:
                    base_fields += [(alternate_field, alternate_field)]
        valid_fields = []
        for field in base_fields:
            if '__' in field[0]:
                relation, rel_field = field[0].split('__')
                try:
                    # check if the field is a relation
                    rel = queryset.model._meta.get_field(relation).rel
                    if rel:
                        # if the field doesn't exist the
                        # call will throw an exception
                        rel.to._meta.get_field(rel_field)
                        valid_fields.append(field)
                except FieldDoesNotExist:
                    pass
            elif field[0] in model_fields:
                valid_fields.append(field)
        return tuple(valid_fields)

    def get_ordering(self, request, queryset, view):
        # We use an alternate ordering if the fields are not present
        # in the second model.
        # (ex: Organization.full_name vs. User.first_name)
        ordering = self.remove_invalid_fields(
            queryset, self.get_default_ordering(view), view, request)
        default_ordering = list(ordering)
        params = request.query_params.getlist(self.ordering_param)
        if params:
            if isinstance(params, six.string_types):
                params = params.split(',')
            fields = [param.strip() for param in params]
            alternate_fields = getattr(view, 'alternate_fields', {})
            for field in fields:
                reverse = False
                if field.startswith('-'):
                    field = field[1:]
                    reverse = True
                alternate_field = alternate_fields.get(field, None)
                if alternate_field:
                    if reverse:
                        if isinstance(alternate_field, (list, tuple)):
                            fields += ['-%s' % item for item in alternate_field]
                        else:
                            fields += ['-%s' % alternate_field]
                    else:
                        if isinstance(alternate_field, (list, tuple)):
                            fields += alternate_field
                        else:
                            fields += [alternate_field]
            ordering = self.remove_invalid_fields(
                queryset, fields, view, request) + default_ordering
        LOGGER.debug("[OrderingFilter] params=%s, default_ordering=%s,"\
            " ordering_fields=%s", params, default_ordering, ordering)
        return ordering


class SortableSearchableFilterBackend(object):

    def __init__(self, sort_fields, search_fields):
        self.sort_fields = sort_fields
        self.search_fields = search_fields

    def __call__(self):
        return self

    def filter_queryset(self, request, queryset, view):
        #pylint:disable=no-self-use,unused-argument
        return queryset

    def get_schema_fields(self, view):
        #pylint:disable=unused-argument
        assert coreapi is not None, 'coreapi must be installed to use'\
            ' `get_schema_fields()`'
        assert coreschema is not None, 'coreschema must be installed '\
            'to use `get_schema_fields()`'
        sort_fields_description = "sort by %s" % ', '.join([
            field[1] for field in self.sort_fields])
        search_fields_description = "search for matching text in %s"  % (
            ', '.join([field_name for field_name in self.search_fields]))

        fields = [
            coreapi.Field(
                name='o',
                required=False,
                location='query',
                schema=coreschema.String(
                    title='O',
                    description=force_text(sort_fields_description)
                )
            ),
            coreapi.Field(
                name='ot',
                required=False,
                location='query',
                schema=coreschema.String(
                    title='OT',
                    description=force_text(
                        "sort by natural ascending or descending order")
                )
            ),
            coreapi.Field(
                name='q',
                required=False,
                location='query',
                schema=coreschema.String(
                    title='Q',
                    description=force_text(search_fields_description)
                )
            )
        ]
        return fields


class SortableDateRangeSearchableFilterBackend(SortableSearchableFilterBackend):

    def __init__(self, sort_fields, search_fields):
        super(SortableDateRangeSearchableFilterBackend, self).__init__(
            sort_fields, search_fields)

    def get_schema_fields(self, view):
        fields = super(SortableDateRangeSearchableFilterBackend,
            self).get_schema_fields(view)
        fields += [
            coreapi.Field(
                name='start_at',
                required=False,
                location='query',
                schema=coreschema.String(
                    title='StartAt',
                    description=force_text("date/time in ISO format"\
                        " after which records were created.")
                )
            ),
            coreapi.Field(
                name='ends_at',
                required=False,
                location='query',
                schema=coreschema.String(
                    title='EndsAt',
                    description=force_text("date/time in ISO format"\
                        " before which records were created.")
                )
            ),
        ]
        return fields
