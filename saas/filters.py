# Copyright (c) 2021, DjaoDjin inc.
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
from django.utils.timezone import utc
from rest_framework.filters import (OrderingFilter as BaseOrderingFilter,
    SearchFilter as BaseSearchFilter, BaseFilterBackend)
from rest_framework.compat import distinct

from . import settings
from .compat import force_str, six
from .utils import datetime_or_now, parse_tz

LOGGER = logging.getLogger(__name__)


class SearchFilter(BaseSearchFilter):

    search_field_param = settings.SEARCH_FIELDS_PARAM

    def get_query_fields(self, request):
        return request.query_params.getlist(self.search_field_param)

    @staticmethod
    def filter_valid_fields(queryset, fields, view):
        #pylint:disable=protected-access
        model_fields = set([
            field.name for field in queryset.model._meta.get_fields()])
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

        valid_fields = []
        for field in fields:
            if '__' in field:
                relation, rel_field = field.split('__')
                try:
                    # check if the field is a relation
                    rel = queryset.model._meta.get_field(relation).remote_field
                    if rel:
                        # if the field doesn't exist the
                        # call will throw an exception
                        rel.model._meta.get_field(rel_field)
                        valid_fields.append(field)
                except FieldDoesNotExist:
                    pass
            elif field in model_fields:
                valid_fields.append(field)

        return tuple(valid_fields)

    def get_valid_fields(self, request, queryset, view, context=None):
        #pylint:disable=protected-access,unused-argument
        if context is None:
            context = {}

        fields = self.get_query_fields(request)
        # client-supplied fields take precedence
        if fields:
            fields = self.filter_valid_fields(queryset, fields, view)
        # if there are no fields (due to empty query params or wrong
        # fields we fallback to fields specified in the view
        if not fields:
            fields = getattr(view, 'search_fields', [])
            fields = self.filter_valid_fields(queryset, fields, view)
        return fields

    def filter_queryset(self, request, queryset, view):
        search_fields = self.get_valid_fields(request, queryset, view)
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

    def get_schema_operation_parameters(self, view):
        search_fields = getattr(view, 'search_fields', [])
        search_fields_description = "search for matching text in %s"  % (
            ', '.join(search_fields))
        return [
            {
                'name': self.search_param,
                'required': False,
                'in': 'query',
                'description': force_str(search_fields_description),
                'schema': {
                    'type': 'string',
                },
            },
        ]


class OrderingFilter(BaseOrderingFilter):

    def get_valid_fields(self, queryset, view, context=None):
        #pylint:disable=protected-access
        if context is None:
            context = {}

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
                    rel = queryset.model._meta.get_field(relation).remote_field
                    if rel:
                        # if the field doesn't exist the
                        # call will throw an exception
                        rel.model._meta.get_field(rel_field)
                        valid_fields.append(field)
                except FieldDoesNotExist:
                    pass
            elif field[0] in model_fields:
                valid_fields.append(field)
        return tuple(valid_fields)

    def remove_invalid_fields(self, queryset, fields, view, request):
        valid_fields = {item[1]: item[0]
            for item in self.get_valid_fields(
                queryset, view, {'request': request})}
        ordering = []
        for term in fields:
            alias = term
            reverse = False
            if alias.startswith('-'):
                alias = alias[1:]
                reverse = True
            real_field = valid_fields.get(alias)
            if real_field:
                if reverse:
                    real_field = '-' + real_field
                ordering.append(real_field)
        return ordering

    def get_ordering(self, request, queryset, view):
        # We use an alternate ordering if the fields are not present
        # in the second model.
        # (ex: Organization.full_name vs. User.first_name)
        ordering = []
        default = self.get_default_ordering(view)
        if default:
            ordering = self.remove_invalid_fields(
                queryset, default, view, request)
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

    def get_schema_operation_parameters(self, view):
        # validating presence of coreapi and coreschema
        super(OrderingFilter, self).get_schema_fields(view)
        ordering_fields = getattr(view, 'ordering_fields', [])
        sort_fields_description = "sort by %s. If a field is preceded by"\
            " a minus sign ('-'), the order will be reversed. Multiple 'o'"\
            " parameters can be specified to produce a stable"\
            " result." % ', '.join([field[1] for field in ordering_fields])
        return [
            {
                'name': self.ordering_param,
                'required': False,
                'in': 'query',
                'description': force_str(sort_fields_description),
                'schema': {
                    'type': 'string',
                },
            },
        ]


class DateRangeFilter(BaseFilterBackend):

    forced_date_range = True
    date_field = 'created_at'
    alternate_date_field = 'date_joined'
    start_at_param = 'start_at'
    ends_at_param = 'ends_at'

    def get_params(self, request, view):
        tz_ob = parse_tz(request.GET.get('timezone'))
        if not tz_ob:
            tz_ob = utc

        ends_at = request.GET.get(self.ends_at_param)
        start_at = request.GET.get(self.start_at_param)
        forced_date_range = getattr(view, 'forced_date_range',
            self.forced_date_range)
        if forced_date_range or ends_at:
            if ends_at is not None:
                ends_at = ends_at.strip('"')
            ends_at = datetime_or_now(ends_at)
            ends_at = ends_at.astimezone(tz_ob)
        if start_at:
            start_at = datetime_or_now(start_at.strip('"'))
            start_at = start_at.astimezone(tz_ob)
        return start_at, ends_at

    def get_date_field(self, model):
        #pylint:disable=protected-access
        model_fields = set([
            field.name for field in model._meta.get_fields()])
        if self.date_field in model_fields:
            return self.date_field
        if self.alternate_date_field in model_fields:
            return self.alternate_date_field
        return None

    def filter_queryset(self, request, queryset, view):
        start_at, ends_at = self.get_params(request, view)
        field = self.get_date_field(queryset.model)
        if not field:
            return queryset
        kwargs = {}
        if ends_at:
            kwargs.update({'%s__lt' % field: ends_at})
        if start_at:
            kwargs.update({'%s__gte' % field: start_at})
        return queryset.filter(**kwargs)

    def get_schema_operation_parameters(self, view):
        fields = super(DateRangeFilter,
            self).get_schema_operation_parameters(view)
        fields += [
            {
                'name': 'start_at',
                'required': False,
                'in': 'query',
                'description': force_str("date/time in ISO format"\
                        " after which records were created."),
                'schema': {
                    'type': 'string',
                },
            },
            {
                'name': 'ends_at',
                'required': False,
                'in': 'query',
                'description': force_str("date/time in ISO format"\
                        " before which records were created."),
                'schema': {
                    'type': 'string',
                },
            }
        ]
        return fields
