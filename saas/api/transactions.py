# Copyright (c) 2016, DjaoDjin inc.
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

import dateutil
from django.db.models import Q
from extra_views.contrib.mixins import SearchableListMixin, SortableListMixin
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from ..humanize import as_money
from ..mixins import (DateRangeMixin, OrganizationMixin, ProviderMixin,
    as_html_description)
from ..models import Transaction, sum_dest_amount, sum_orig_amount

#pylint: disable=no-init
#pylint: disable=old-style-class


class TransactionSerializer(serializers.ModelSerializer):

    orig_organization = serializers.SlugRelatedField(
        read_only=True, slug_field='slug')
    dest_organization = serializers.SlugRelatedField(
        read_only=True, slug_field='slug')
    description = serializers.CharField(source='descr', read_only=True)
    amount = serializers.CharField(source='dest_amount', read_only=True)
    is_debit = serializers.CharField(source='dest_amount', read_only=True)

    def _is_debit(self, transaction):
        """
        True if the transaction can be tagged as a debit. That is
        it is either payable by the organization or the transaction
        moves from a Funds account to the organization's Expenses account.
        """
        #pylint: disable=no-member
        if hasattr(self.context['view'], 'organization'):
            return transaction.is_debit(self.context['view'].organization)
        return False

    def to_representation(self, obj):
        ret = super(TransactionSerializer, self).to_representation(obj)
        is_debit = self._is_debit(obj)
        if is_debit:
            amount = as_money(obj.orig_amount, '-%s' % obj.orig_unit)
        else:
            amount = as_money(obj.dest_amount, obj.dest_unit)
        ret.update({
            'description': as_html_description(obj),
            'is_debit': is_debit,
            'amount': amount})
        return ret

    class Meta:
        model = Transaction
        fields = ('created_at', 'description', 'amount', 'is_debit',
            'orig_account', 'orig_organization', 'orig_amount', 'orig_unit',
            'dest_account', 'dest_organization', 'dest_amount', 'dest_unit')


class BalancePagination(PageNumberPagination):

    def paginate_queryset(self, queryset, request, view=None):
        if view.selector is not None:
            dest_totals = sum_dest_amount(queryset.filter(
                dest_account__icontains=view.selector))
            orig_totals = sum_orig_amount(queryset.filter(
                orig_account__icontains=view.selector))
        else:
            dest_totals = sum_dest_amount(queryset)
            orig_totals = sum_orig_amount(queryset)
        self.balance = dest_totals['amount'] - orig_totals['amount']
        return super(BalancePagination, self).paginate_queryset(
            queryset, request, view=view)

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('balance', self.balance),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


class TotalPagination(PageNumberPagination):

    def paginate_queryset(self, queryset, request, view=None):
        self.totals = view.totals
        return super(TotalPagination, self).paginate_queryset(
            queryset, request, view=view)

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('total', self.totals['amount']),
            ('unit', self.totals['unit']),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


class TotalAnnotateMixin(object):

    def get_queryset(self):
        queryset = super(TotalAnnotateMixin, self).get_queryset()
        self.totals = sum_orig_amount(queryset)
        return queryset


class TransactionFilterMixin(DateRangeMixin, SearchableListMixin):
    """
    ``Transaction`` list result of a search query, filtered by dates.
    """

    search_fields = ['descr',
                     'orig_organization__full_name',
                     'dest_organization__full_name']


class SmartTransactionListMixin(SortableListMixin, TransactionFilterMixin):
    """
    ``Transaction`` list which is also searchable and sortable.
    """

    sort_fields_aliases = [('descr', 'description'),
                           ('dest_amount', 'amount'),
                           ('dest_organization__slug', 'dest_organization'),
                           ('dest_account', 'dest_account'),
                           ('orig_organization__slug', 'orig_organization'),
                           ('orig_account', 'orig_account'),
                           ('created_at', 'created_at')]


class TransactionQuerysetMixin(object):

    def get_queryset(self):
        self.selector = self.request.GET.get('selector', None)
        if self.selector is not None:
            return Transaction.objects.filter(
                Q(dest_account__icontains=self.selector)
                | Q(orig_account__icontains=self.selector))
        return Transaction.objects.all()


class TransactionListAPIView(SmartTransactionListMixin,
                             TransactionQuerysetMixin, ListAPIView):
    """
    GET queries all ``Transaction`` recorded in the ledger.

    The queryset can be further filtered to a range of dates between
    ``start_at`` and ``ends_at``.

    The queryset can be further filtered by passing a ``q`` parameter.
    The value in ``q`` will be matched against:

      - Transaction.descr
      - Transaction.orig_organization.full_name
      - Transaction.dest_organization.full_name

    The result queryset can be ordered by:

      - Transaction.created_at
      - Transaction.descr
      - Transaction.dest_amount

    **Example request**:

    .. sourcecode:: http

        GET /api/billing/transactions?start_at=2015-07-05T07:00:00.000Z\
&o=date&ot=desc

    **Example response**:

    .. sourcecode:: http

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2015-08-01T00:00:00Z",
                    "description": "Charge for 4 periods",
                    "amount": "($356.00)",
                    "is_debit": true,
                    "orig_account": "Liability",
                    "orig_organization": "xia",
                    "orig_amount": 112120,
                    "orig_unit": "usd",
                    "dest_account": "Funds",
                    "dest_organization": "stripe",
                    "dest_amount": 112120,
                    "dest_unit": "usd"
                }
            ]
        }
    """
    serializer_class = TransactionSerializer
    pagination_class = BalancePagination


class BillingsQuerysetMixin(OrganizationMixin):

    def get_queryset(self):
        """
        Get the list of transactions for this organization.
        """
        return Transaction.objects.by_customer(self.organization)


class BillingsAPIView(SmartTransactionListMixin,
                      BillingsQuerysetMixin, ListAPIView):
    """
    GET queries all ``Transaction`` associated to ``:organization`` while
    the organization acts as a subscriber in the relation.

    The queryset can be further filtered to a range of dates between
    ``start_at`` and ``ends_at``.

    The queryset can be further filtered by passing a ``q`` parameter.
    The value in ``q`` will be matched against:

      - Transaction.descr
      - Transaction.orig_organization.full_name
      - Transaction.dest_organization.full_name

    The result queryset can be ordered by:

      - Transaction.created_at
      - Transaction.descr
      - Transaction.dest_amount

    **Example request**:

    .. sourcecode:: http

        GET /api/billing/xia/billings?start_at=2015-07-05T07:00:00.000Z\
&o=date&ot=desc

    **Example response**:

    .. sourcecode:: http

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2015-08-01T00:00:00Z",
                    "description": "Charge for 4 periods",
                    "amount": "($356.00)",
                    "is_debit": true,
                    "orig_account": "Liability",
                    "orig_organization": "xia",
                    "orig_amount": 112120,
                    "orig_unit": "usd",
                    "dest_account": "Funds",
                    "dest_organization": "stripe",
                    "dest_amount": 112120,
                    "dest_unit": "usd"
                }
            ]
        }
    """

    serializer_class = TransactionSerializer


class ReceivablesQuerysetMixin(ProviderMixin):

    def get_queryset(self):
        """
        Get the list of transactions for this organization.
        """
        return self.provider.receivables().filter(orig_amount__gt=0)


class ReceivablesListAPIView(SortableListMixin, TotalAnnotateMixin,
                             TransactionFilterMixin, ReceivablesQuerysetMixin,
                             ListAPIView):
    """
    GET queries all receivables for a provider.

    The queryset can be further filtered to a range of dates between
    ``start_at`` and ``ends_at``.

    The queryset can be further filtered by passing a ``q`` parameter.
    The value in ``q`` will be matched against:

      - Transaction.descr
      - Transaction.orig_organization.full_name
      - Transaction.dest_organization.full_name

    The result queryset can be ordered by:

      - Transaction.created_at
      - Transaction.descr
      - Transaction.dest_amount

    **Example request**:

    .. sourcecode:: http

        GET /api/billing/cowork/receivables?start_at=2015-07-05T07:00:00.000Z\
&o=date&ot=desc

    **Example response**:

    .. sourcecode:: http

        {
            "count": 1,
            "total": "112120",
            "unit": "usd",
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2015-08-01T00:00:00Z",
                    "description": "Charge <a href=\"/billing/cowork/receipt/\
1123\">1123</a> distribution for demo562-open-plus",
                    "amount": "112120",
                    "is_debit": false,
                    "orig_account": "Funds",
                    "orig_organization": "stripe",
                    "orig_amount": 112120,
                    "orig_unit": "usd",
                    "dest_account": "Funds",
                    "dest_organization": "cowork",
                    "dest_amount": 112120,
                    "dest_unit": "usd"
                }
            ]
        }
    """
    sort_fields_aliases = [('descr', 'description'),
                           ('dest_amount', 'amount'),
                           ('dest_organization__slug', 'dest_organization'),
                           ('dest_account', 'dest_account'),
                           ('orig_organization__slug', 'orig_organization'),
                           ('orig_account', 'orig_account'),
                           ('created_at', 'created_at')]

    natural_period = dateutil.relativedelta.relativedelta(days=-1)
    serializer_class = TransactionSerializer
    pagination_class = TotalPagination


class TransferQuerysetMixin(ProviderMixin):

    def get_queryset(self):
        """
        Get the list of transactions for this organization.
        """
        return self.organization.get_transfers()


class TransferListAPIView(SmartTransactionListMixin, TransferQuerysetMixin,
                          ListAPIView):
    """
    GET queries all ``Transaction`` associated to ``:organization`` while
    the organization acts as a provider in the relation.

    The queryset can be further filtered to a range of dates between
    ``start_at`` and ``ends_at``.

    The queryset can be further filtered by passing a ``q`` parameter.
    The value in ``q`` will be matched against:

      - Transaction.descr
      - Transaction.orig_organization.full_name
      - Transaction.dest_organization.full_name

    The result queryset can be ordered by:

      - Transaction.created_at
      - Transaction.descr
      - Transaction.dest_amount

    **Example request**:

    .. sourcecode:: http

        GET /api/billing/cowork/transfers?start_at=2015-07-05T07:00:00.000Z\
&o=date&ot=desc

    **Example response**:

    .. sourcecode:: http

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2015-08-01T00:00:00Z",
                    "description": "Charge <a href=\"/billing/cowork/receipt/\
1123\">1123</a> distribution for demo562-open-plus",
                    "amount": "$1121.20",
                    "is_debit": false,
                    "orig_account": "Funds",
                    "orig_organization": "stripe",
                    "orig_amount": 112120,
                    "orig_unit": "usd",
                    "dest_account": "Funds",
                    "dest_organization": "cowork",
                    "dest_amount": 112120,
                    "dest_unit": "usd"
                }
            ]
        }
    """
    serializer_class = TransactionSerializer
