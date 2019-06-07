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

"""
CSV download view basics.
"""

from __future__ import unicode_literals

import csv
from decimal import Decimal
from io import BytesIO, StringIO

from django.http import HttpResponse
from django.utils import six
from django.views.generic import View
from rest_framework.request import Request

from ..api.coupons import SmartCouponListMixin, CouponQuerysetMixin
from ..api.transactions import (BillingsQuerysetMixin,
    SmartTransactionListMixin, TransactionQuerysetMixin, TransferQuerysetMixin)
from ..api.users import RegisteredQuerysetMixin
from .. import humanize
from ..managers.metrics import (abs_monthly_balances, monthly_balances,
    month_periods)
from ..mixins import (MetricsMixin, ChurnedQuerysetMixin,
    SubscriptionSmartListMixin, SubscribedQuerysetMixin, UserSmartListMixin)
from ..models import BalanceLine, CartItem
from ..utils import datetime_or_now


class CSVDownloadView(View):

    basename = 'download'
    headings = []

    @staticmethod
    def encode(text):
        if six.PY2:
            return text.encode('utf-8')
        return text

    def filter_queryset(self, queryset):
        """
        Recreating a GenericAPIView.filter_queryset functionality here
        """
        # creating a DRF-compatible request object
        request = Request(self.request)
        for backend in list(self.filter_backends):
            queryset = backend().filter_queryset(request, queryset, self)
        return queryset

    def get(self, *args, **kwargs): #pylint: disable=unused-argument
        if six.PY2:
            content = BytesIO()
        else:
            content = StringIO()
        csv_writer = csv.writer(content)
        csv_writer.writerow([self.encode(head)
            for head in self.get_headings()])
        qs = self.filter_queryset(self.get_queryset())
        for record in qs:
            csv_writer.writerow(self.queryrow_to_columns(record))
        content.seek(0)
        resp = HttpResponse(content, content_type='text/csv')
        resp['Content-Disposition'] = \
            'attachment; filename="{}"'.format(
                self.get_filename())
        return resp

    def get_headings(self):
        return self.headings

    def get_queryset(self):
        # Note: this should take the same arguments as for
        # Searchable and SortableListMixin in "extra_views"
        raise NotImplementedError

    def get_filename(self):
        return datetime_or_now().strftime(self.basename + '-%Y%m%d.csv')

    def queryrow_to_columns(self, record):
        raise NotImplementedError


class BalancesDownloadView(MetricsMixin, CSVDownloadView):
    """
    Export balance metrics as a CSV file.
    """
    queryname = 'balances'

    def get_headings(self):
        return ['Title'] + [str(end_period) for end_period in month_periods(
            from_date=self.ends_at, tz=self.timezone)]

    def get_queryset(self):
        report = self.kwargs.get('report')
        return BalanceLine.objects.filter(report=report).order_by('rank')

    def queryrow_to_columns(self, record):
        balance_line = record
        if balance_line.is_positive:
            balances_func = abs_monthly_balances
        else:
            balances_func = monthly_balances
        if balance_line.selector:
            balances, _ = balances_func(
                like_account=balance_line.selector, until=self.ends_at)
            row = [balance_line.title] + [item[1] for item in balances]
        else:
            # means we have a heading only
            row = [balance_line.title]
        return row


class CouponMetricsDownloadView(SmartCouponListMixin, CouponQuerysetMixin,
                                CSVDownloadView):

    headings = [
        'Code',
        'Percentage',
        'Name',
        'Email',
        'Plan',
    ]

    def get_headings(self):
        return self.headings

    def get_filename(self):
        return datetime_or_now().strftime('coupons-%Y%m%d.csv')

    def get_queryset(self):
        '''
        Return CartItems related to the Coupon specified in the URL.
        '''
        # invoke SmartCouponListMixin to get the coupon specified by URL params
        coupons = super(CouponMetricsDownloadView, self).get_queryset()
        # get related CartItems
        return CartItem.objects.filter(coupon__in=coupons)

    def queryrow_to_columns(self, record):
        cartitem = record
        if cartitem.user:
            claim_code = 'CLAIMED'
            email = cartitem.user.email
            full_name = ' '.join([
                cartitem.user.first_name, cartitem.user.last_name])
        else:
            claim_code = cartitem.claim_code
            full_name = cartitem.full_name
            email = cartitem.sync_on
        return [
            self.encode(cartitem.coupon.code),
            cartitem.coupon.percent,
            self.encode(full_name),
            self.encode(email),
            self.encode(cartitem.plan.slug),
            self.encode(claim_code)]


class RegisteredBaseDownloadView(RegisteredQuerysetMixin, CSVDownloadView):

    def get_headings(self):
        return ['First name', 'Last name', 'Email', 'Registration Date']

    def get_filename(self):
        return 'registered-{}.csv'.format(datetime_or_now().strftime('%Y%m%d'))

    def queryrow_to_columns(self, record):
        user = record
        return [
            self.encode(user.first_name),
            self.encode(user.last_name),
            self.encode(user.email),
            user.date_joined.date(),
        ]


class RegisteredDownloadView(UserSmartListMixin, RegisteredBaseDownloadView):

    pass


class SubscriptionBaseDownloadView(CSVDownloadView):

    subscriber_type = None

    def get_queryset(self):
        raise NotImplementedError()

    def get_headings(self):
        return ['Name', 'Email', 'Plan', 'Since', 'Until']

    def get_filename(self):
        return 'subscribers-{}-{}.csv'.format(
            self.subscriber_type, datetime_or_now().strftime('%Y%m%d'))

    def queryrow_to_columns(self, record):
        subscription = record
        return [
            self.encode(subscription.organization.full_name),
            self.encode(subscription.organization.email),
            self.encode(subscription.plan.title),
            subscription.created_at.date(),
            subscription.ends_at.date(),
        ]


class ActiveSubscriptionBaseDownloadView(SubscribedQuerysetMixin,
                                         SubscriptionBaseDownloadView):

    subscriber_type = 'active'

class ActiveSubscriptionDownloadView(SubscriptionSmartListMixin,
                                     ActiveSubscriptionBaseDownloadView):

    pass


class ChurnedSubscriptionBaseDownloadView(ChurnedQuerysetMixin,
                                         SubscriptionBaseDownloadView):

    subscriber_type = 'churned'


class ChurnedSubscriptionDownloadView(SubscriptionSmartListMixin,
                                      ChurnedSubscriptionBaseDownloadView):

    pass


class TransactionDownloadView(SmartTransactionListMixin,
                           TransactionQuerysetMixin, CSVDownloadView):

    basename = 'transactions'

    headings = [
        'created_at',
        'dest_amount',
        'dest_unit',
        'dest_organization',
        'dest_account',
        'orig_amount',
        'orig_unit',
        'orig_organization',
        'orig_account',
        'description'
    ]

    def get_queryset(self):
        return super(TransactionDownloadView, self).get_queryset().order_by(
            '-created_at')

    def queryrow_to_columns(self, record):
        transaction = record
        return [
            transaction.created_at.date(),
            self.encode(humanize.as_money(
                transaction.dest_amount, transaction.dest_unit,
                negative_format="-%s")),
            self.encode(transaction.dest_unit),
            self.encode(transaction.dest_organization.printable_name),
            self.encode(transaction.dest_account),
            self.encode(humanize.as_money(
                transaction.orig_amount, transaction.orig_unit,
                negative_format="-%s")),
            self.encode(transaction.orig_unit),
            self.encode(transaction.orig_organization.printable_name),
            self.encode(transaction.orig_account),
            self.encode(('"%s"' % transaction.descr.replace(
                '\\', '\\\\').replace('"', '\"')))
        ]


class BillingStatementDownloadView(SmartTransactionListMixin,
                           BillingsQuerysetMixin, CSVDownloadView):

    basename = 'statement'
    headings = [
        'CreatedAt',
        'Amount',
        'Unit',
        'Description'
    ]

    def queryrow_to_columns(self, record):
        transaction = record
        return [
            transaction.created_at.date(),
            '{:.2f}'.format(
                (-1 if transaction.is_debit(self.organization) else 1) *
                # XXX integer division
                Decimal(transaction.dest_amount) / 100),
            self.encode(transaction.dest_unit),
            self.encode(('"%s"' % transaction.descr.replace(
                '\\', '\\\\').replace('"', '\"')))
        ]


class TransferDownloadView(SmartTransactionListMixin,
                           TransferQuerysetMixin, CSVDownloadView):

    basename = 'transfers'
    headings = [
        'CreatedAt',
        'Amount',
        'Unit',
        'Description'
    ]

    def queryrow_to_columns(self, record):
        transaction = record
        return [
            transaction.created_at.date(),
            '{:.2f}'.format(
                (-1 if transaction.is_debit(self.organization) else 1) *
                # XXX integer division
                Decimal(transaction.dest_amount) / 100),
            self.encode(transaction.dest_unit),
            self.encode(('"%s"' % transaction.descr.replace(
                '\\', '\\\\').replace('"', '\"')))
        ]
