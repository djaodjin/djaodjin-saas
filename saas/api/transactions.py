# Copyright (c) 2014, DjaoDjin inc.
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

from django.db.models import Q
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.generics import ListAPIView
from extra_views.contrib.mixins import SearchableListMixin, SortableListMixin

from saas.humanize import as_html_description, as_money
from saas.models import Transaction
from saas.mixins import OrganizationMixin, ProviderMixin

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

    @staticmethod
    def transform_description(obj, value):
        #pylint: disable=unused-argument
        return as_html_description(obj)

    def transform_is_debit(self, obj, value):
        #pylint: disable=unused-argument
        return self._is_debit(obj)

    def _is_debit(self, transaction):
        """
        True if the transaction can be tagged as a debit. That is
        it is either payable by the organization or the transaction
        moves from a Funds account to the organization's Expenses account.
        """
        #pylint: disable=no-member
        organization = self.context['view'].organization
        return ((transaction.dest_organization == organization       # customer
                 and transaction.dest_account == Transaction.EXPENSES)
                or (transaction.orig_organization == organization    # provider
                 and transaction.orig_account == Transaction.FUNDS))

    def transform_amount(self, obj, value):
        #pylint: disable=unused-argument
        return as_money(obj.dest_amount, '-%s' % obj.dest_unit
            if self._is_debit(obj) else obj.dest_unit)

    class Meta:
        model = Transaction
        fields = ('created_at', 'description', 'amount', 'is_debit',
            'orig_account', 'orig_organization', 'orig_amount', 'orig_unit',
            'dest_account', 'dest_organization', 'dest_amount', 'dest_unit')


class SmartTransactionListMixin(SearchableListMixin, SortableListMixin):
    """
    Subscriber list which is also searchable and sortable.
    """
    search_fields = ['created_at',
                     'descr',
                     'orig_organization__full_name',
                     'dest_organization__full_name']

    sort_fields_aliases = [('created_at', 'date'),
                           ('descr', 'description'),
                           ('dest_amount', 'amount')]


class TransactionListBaseAPIView(OrganizationMixin, ListAPIView):

    def get_queryset(self):
        """
        Get the list of transactions for this organization.
        """
        self.organization = self.get_organization()
        queryset = Transaction.objects.filter(
            (Q(dest_organization=self.organization)
             & (Q(dest_account=Transaction.PAYABLE) # Only customer side
                | Q(dest_account=Transaction.EXPENSES)))
            |(Q(orig_organization=self.organization)
              & Q(orig_account=Transaction.REFUNDED)))
        return queryset


class TransactionListAPIView(SmartTransactionListMixin,
                             TransactionListBaseAPIView):

    serializer_class = TransactionSerializer
    paginate_by = 25


class TransferListBaseAPIView(ProviderMixin, ListAPIView):

    def get_queryset(self):
        """
        Get the list of transactions for this organization.
        """
        self.organization = self.get_organization()
        queryset = Transaction.objects.filter(
            # All transactions involving Funds
            ((Q(orig_organization=self.organization)
              & Q(orig_account=Transaction.FUNDS))
            | (Q(dest_organization=self.organization)
              & Q(dest_account=Transaction.FUNDS))))
        return queryset


class TransferListAPIView(SmartTransactionListMixin, TransferListBaseAPIView):

    serializer_class = TransactionSerializer
    paginate_by = 25
