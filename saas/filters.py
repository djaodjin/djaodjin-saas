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

import operator
from functools import reduce

from django.db import models
from django.utils import six
from django.utils.encoding import force_text
from rest_framework.compat import coreapi, coreschema
from rest_framework.filters import (OrderingFilter as BaseOrderingFilter,
    SearchFilter as BaseSearchFilter)
from rest_framework.compat import distinct

class SearchFilter(BaseSearchFilter):

    def get_valid_fields(self, queryset, view, context={}):
        model_fields = set([
            field.name for field in queryset.model._meta.get_fields()])
        base_fields = getattr(view, 'search_fields', [])
        valid_fields = tuple([
            field for field in base_fields if field in model_fields])
        return valid_fields

    def filter_queryset(self, request, queryset, view):
        search_fields = self.get_valid_fields(queryset, view)
        search_terms = self.get_search_terms(request)

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
        base_fields = super(OrderingFilter, self).get_valid_fields(
            queryset, view, context=context)
        valid_fields = tuple([
            field for field in base_fields if field[0] in model_fields])
        return valid_fields

    def get_ordering(self, request, queryset, view):
        ordering = None
        params = request.query_params.get(self.ordering_param)
        if params:
            fields = [param.strip() for param in params.split(',')]
            if 'created_at' in fields or '-created_at' in fields:
                model_fields = set([
                    field.name for field in queryset.model._meta.get_fields()])
                if 'date_joined' in model_fields:
                    fields = ['date_joined' if field == 'created_at' else (
                        '-date_joined' if field == '-created_at' else field)
                        for field in fields]
            ordering = self.remove_invalid_fields(
                queryset, fields, view, request)
        if not ordering:
            # We use an alternate ordering if the fields are not present
            # in the second model.
            # (ex: Organization.full_name vs. User.first_name)
            ordering = self.remove_invalid_fields(
                queryset, self.get_default_ordering(view), view, request)
        if not ordering:
            ordering = view.alternate_ordering
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
