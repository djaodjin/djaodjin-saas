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

from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from . import settings
from .models import (sum_dest_amount, sum_orig_amount, sum_balance_amount,
    Transaction)


class BalancePagination(PageNumberPagination):
    """
    Decorate the results of an API call with balance on an account
    containing *selector*.
    """

    def paginate_queryset(self, queryset, request, view=None):
        self.start_at = view.start_at
        self.ends_at = view.ends_at
        if view.selector is not None:
            dest_totals = sum_dest_amount(queryset.filter(
                dest_account__icontains=view.selector))
            orig_totals = sum_orig_amount(queryset.filter(
                orig_account__icontains=view.selector))
        else:
            dest_totals = sum_dest_amount(queryset)
            orig_totals = sum_orig_amount(queryset)
        balance = sum_balance_amount(dest_totals, orig_totals)
        self.balance_amount = balance['amount']
        self.balance_unit = balance['unit']
        return super(BalancePagination, self).paginate_queryset(
            queryset, request, view=view)

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('start_at', self.start_at),
            ('ends_at', self.ends_at),
            ('balance_amount', self.balance_amount),
            ('balance_unit', self.balance_unit),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'start_at': {
                    'type': 'string',
                    'format': 'date',
                    'description': "Start of the date range for which"\
                        " the balance was computed"
                },
                'ends_at': {
                    'type': 'string',
                    'format': 'date',
                    'description': "End of the date range for which"\
                        " the balance was computed"
                },
                'balance_amount': {
                    'type': 'integer',
                    'description': "balance of all transactions in cents"\
                        " (i.e. 100ths) of unit"
                },
                'balance_unit': {
                    'type': 'integer',
                    'description': "three-letter ISO 4217 code"\
                        " for currency unit (ex: usd)"
                },
                'count': {
                    'type': 'integer',
                    'description': "The number of records"
                },
                'next': {
                    'type': 'string',
                    'description': "API end point to get the next page"\
                        "of records matching the query",
                    'nullable': True,
                    'format': 'uri',
                },
                'previous': {
                    'type': 'string',
                    'description': "API end point to get the previous page"\
                        "of records matching the query",
                    'nullable': True,
                    'format': 'uri',
                },
                'results': schema,
            },
        }


class RoleListPagination(PageNumberPagination):

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('invited_count', self.request.invited_count),
            ('requested_count', self.request.requested_count),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'invited_count': {
                    'type': 'integer',
                    'description': "Number of user invited to have a role"
                },
                'requested_count': {
                    'type': 'integer',
                    'description': "Number of user requesting a role"
                },
                'count': {
                    'type': 'integer',
                    'description': "The number of records"
                },
                'next': {
                    'type': 'string',
                    'description': "API end point to get the next page"\
                        "of records matching the query",
                    'nullable': True,
                    'format': 'uri',
                },
                'previous': {
                    'type': 'string',
                    'description': "API end point to get the previous page"\
                        "of records matching the query",
                    'nullable': True,
                    'format': 'uri',
                },
                'results': schema,
            },
        }


class StatementBalancePagination(PageNumberPagination):
    """
    Decorate the results of an API call with the balance as shown
    in an organization statement.
    """

    def paginate_queryset(self, queryset, request, view=None):
        self.start_at = view.start_at
        self.ends_at = view.ends_at
        self.balance_amount, self.balance_unit \
            = Transaction.objects.get_statement_balance(view.organization)
        return super(StatementBalancePagination, self).paginate_queryset(
            queryset, request, view=view)

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('start_at', self.start_at),
            ('ends_at', self.ends_at),
            ('balance_amount', self.balance_amount),
            ('balance_unit', self.balance_unit),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'start_at': {
                    'type': 'string',
                    'format': 'date',
                    'description': "Start of the date range for which"\
                        " the balance was computed"
                },
                'ends_at': {
                    'type': 'string',
                    'format': 'date',
                    'description': "End of the date range for which"\
                        " the balance was computed"
                },
                'balance_amount': {
                    'type': 'integer',
                    'description': "balance of all transactions in cents"\
                        " (i.e. 100ths) of unit"
                },
                'balance_unit': {
                    'type': 'integer',
                    'description': "three-letter ISO 4217 code"\
                        " for currency unit (ex: usd)"
                },
                'count': {
                    'type': 'integer',
                    'description': "The number of records"
                },
                'next': {
                    'type': 'string',
                    'description': "API end point to get the next page"\
                        "of records matching the query",
                    'nullable': True,
                    'format': 'uri',
                },
                'previous': {
                    'type': 'string',
                    'description': "API end point to get the previous page"\
                        "of records matching the query",
                    'nullable': True,
                    'format': 'uri',
                },
                'results': schema,
            },
        }


class TotalPagination(PageNumberPagination):

    def paginate_queryset(self, queryset, request, view=None):
        self.start_at = view.start_at
        self.ends_at = view.ends_at
        self.totals = view.totals
        return super(TotalPagination, self).paginate_queryset(
            queryset, request, view=view)

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('start_at', self.start_at),
            ('ends_at', self.ends_at),
            ('balance_amount', self.totals['amount']),
            ('balance_unit', self.totals['unit']),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'balance_amount': {
                    'type': 'integer',
                    'description': "The sum of all record amounts (in unit)"
                },
                'balance_unit': {
                    'type': 'integer',
                    'description': "three-letter ISO 4217 code"\
                        " for currency unit (ex: usd)"
                },
                'count': {
                    'type': 'integer',
                    'description': "The number of records"
                },
                'next': {
                    'type': 'string',
                    'description': "API end point to get the next page"\
                        "of records matching the query",
                    'nullable': True,
                    'format': 'uri',
                },
                'previous': {
                    'type': 'string',
                    'description': "API end point to get the previous page"\
                        "of records matching the query",
                    'nullable': True,
                    'format': 'uri',
                },
                'results': schema,
            },
        }


class TypeaheadPagination(PageNumberPagination):

    page_size = settings.MAX_TYPEAHEAD_CANDIDATES

    def paginate_queryset(self, queryset, request, view=None):
        self.count = queryset.count()
        if self.count > self.page_size:
            # returning an empty set if the number of results is greater than
            # MAX_TYPEAHEAD_CANDIDATES
            queryset = queryset.none()
            self.count = 0
        return list(queryset)

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.count),
            ('results', data)
        ]))

    def get_schema_operation_parameters(self, view):
        return []

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'count': {
                    'type': 'integer',
                    'description': "The number of records"
                },
                'results': schema,
            },
        }
