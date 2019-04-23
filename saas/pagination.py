# Copyright (c) 2018, DjaoDjin inc.
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

from .models import sum_dest_amount, sum_orig_amount, sum_balance_amount
from . import settings


class BalancePagination(PageNumberPagination):
    """
    Decorate the results of an API call with balance on an account
    containing *selector*.
    """

    def paginate_queryset(self, queryset, request, view=None):
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
            ('ends_at', self.ends_at),
            ('balance', self.balance_amount),
            ('unit', self.balance_unit),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


class TotalPagination(PageNumberPagination):

    def paginate_queryset(self, queryset, request, view=None):
        self.total = 0
        for charge in queryset:
            self.total += charge.amount
        return super(TotalPagination, self).paginate_queryset(
            queryset, request, view=view)

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('total', self.total),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


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
