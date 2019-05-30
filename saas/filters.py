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
import six
from functools import reduce

from django.db import models
from django.utils import six
from django.utils.encoding import force_text
from rest_framework.compat import coreapi, coreschema
from rest_framework.filters import (OrderingFilter as BaseOrderingFilter,
    SearchFilter as BaseSearchFilter)
from rest_framework.compat import distinct

from . import settings

class SearchFilter(BaseSearchFilter):

    search_field_param = settings.SEARCH_FIELDS_PARAM

    def get_query_fields(self, request):
        fields = request.query_params.get(self.search_field_param, '')
        return fields.replace(',', ' ').split()

    def filter_valid_fields(self, model_fields, fields):
        return tuple([
            field for field in fields if field in model_fields])

    def get_valid_fields(self, queryset, view, context={}):
        model_fields = set([
            field.name for field in queryset.model._meta.get_fields()])
        fields = self.get_query_fields(view.request)
        # client-supplied fields take precedence
        if fields:
            fields = self.filter_valid_fields(model_fields, fields)
        # if there are no fields (due to empty query params or wrong
        # fields we fallback to fields specified in the view
        if not fields:
            fields = getattr(view, 'search_fields', [])
            fields = self.filter_valid_fields(model_fields, fields)
        return fields

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
            ordering = self.get_default_ordering(view)
        if not ordering:
            if hasattr(view, 'alternate_ordering'):
                ordering = view.alternate_ordering
        return ordering

    def remove_invalid_fields(self, queryset, fields, view, request):
        valid_fields = getattr(view, 'ordering_fields', self.ordering_fields)
        if valid_fields is None or valid_fields == '__all__':
            return super(OrderingFilter, self).remove_invalid_fields(
                queryset, fields, view, request)

        aliased_fields = {}
        for field in valid_fields:
            if isinstance(field, six.string_types):
                aliased_fields[field] = field
            else:
                aliased_fields[field[1]] = field[0]

        ordering = []
        for raw_field in fields:
            reverse = raw_field[0] == '-'
            field = raw_field.lstrip('-')
            if field in aliased_fields:
                if reverse:
                    ordering.append('-%s' % aliased_fields[field])
                else:
                    ordering.append(aliased_fields[field])
        return ordering
