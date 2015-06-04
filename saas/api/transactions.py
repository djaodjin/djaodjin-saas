# Copyright (c) 2015, DjaoDjin inc.
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

from rest_framework import serializers
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

    def _is_debit(self, transaction):
        """
        True if the transaction can be tagged as a debit. That is
        it is either payable by the organization or the transaction
        moves from a Funds account to the organization's Expenses account.
        """
        #pylint: disable=no-member
        return transaction.is_debit(self.context['view'].organization)

    def to_representation(self, obj):
        ret = super(TransactionSerializer, self).to_representation(obj)
        ret.update({
            'description': as_html_description(obj),
            'is_debit': self._is_debit(obj),
            'amount': as_money(obj.dest_amount, '-%s' % obj.dest_unit
                        if self._is_debit(obj) else obj.dest_unit)})
        return ret

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


class TransactionQuerysetMixin(OrganizationMixin):

    def get_queryset(self):
        """
        Get the list of transactions for this organization.
        """
        self.organization = self.get_organization()
        return Transaction.objects.by_customer(self.organization)


class TransactionListAPIView(SmartTransactionListMixin,
                             TransactionQuerysetMixin, ListAPIView):

    serializer_class = TransactionSerializer
    paginate_by = 25


class TransferQuerysetMixin(ProviderMixin):

    def get_queryset(self):
        """
        Get the list of transactions for this organization.
        """
        self.organization = self.get_organization()
        return Transaction.objects.by_organization(
            self.organization, Transaction.FUNDS)


class TransferListAPIView(SmartTransactionListMixin, TransferQuerysetMixin,
                          ListAPIView):

    serializer_class = TransactionSerializer
    paginate_by = 25
