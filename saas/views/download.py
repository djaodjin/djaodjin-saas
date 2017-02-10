# Copyright (c) 2017, DjaoDjin inc.
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
from io import StringIO

from django.http import HttpResponse
from django.views.generic import View

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

    def get(self, *args, **kwargs): #pylint: disable=unused-argument
        content = StringIO()
        csv_writer = csv.writer(content)
        print "XXX get_headings=%s" % str(self.get_headings())
        csv_writer.writerow(self.get_headings())
        for record in self.get_queryset():
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
        return ['Title'] + [
            end_period for end_period in month_periods(from_date=self.ends_at)]

    def get_queryset(self):
        report = self.kwargs.get('report')
        return BalanceLine.objects.filter(report=report).order_by('rank')

    def queryrow_to_columns(self, balance_line):
        if balance_line.is_positive:
            balances_func = abs_monthly_balances
        else:
            balances_func = monthly_balances
        return [balance_line.title] + [item[1] for item in balances_func(
            like_account=balance_line.selector, until=self.ends_at)]


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

    def queryrow_to_columns(self, cartitem):
        if cartitem.user:
            claim_code = 'CLAIMED'
            email = cartitem.user.email
            full_name = ' '.join([
                cartitem.user.first_name, cartitem.user.last_name])
        else:
            claim_code = cartitem.claim_code
            full_name = ' '.join([cartitem.first_name, cartitem.last_name])
            email = cartitem.email
        return [
            cartitem.coupon.code.encode('utf-8'),
            cartitem.coupon.percent,
            full_name.encode('utf-8'),
            email.encode('utf-8'),
            cartitem.plan.slug.encode('utf-8'),
            claim_code.encode('utf-8')]


class RegisteredBaseDownloadView(RegisteredQuerysetMixin, CSVDownloadView):

    def get_headings(self):
        return ['First name', 'Last name', 'Email', 'Registration Date']

    def get_filename(self):
        return 'registered-{}.csv'.format(datetime_or_now().strftime('%Y%m%d'))

    def queryrow_to_columns(self, instance):
        return [
            instance.first_name.encode('utf-8'),
            instance.last_name.encode('utf-8'),
            instance.email.encode('utf-8'),
            instance.date_joined.date(),
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

    def queryrow_to_columns(self, instance):
        return [
            instance.organization.full_name.encode('utf-8'),
            instance.organization.email.encode('utf-8'),
            instance.plan.title.encode('utf-8'),
            instance.created_at.date(),
            instance.ends_at.date(),
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

    def queryrow_to_columns(self, transaction):
        return [
            transaction.created_at.date(),
            humanize.as_money(transaction.dest_amount, transaction.dest_unit,
                negative_format="-%s"),
            transaction.dest_unit.encode('utf-8'),
            transaction.dest_organization.printable_name.encode('utf-8'),
            transaction.dest_account.encode('utf-8'),
            humanize.as_money(transaction.orig_amount, transaction.orig_unit,
                negative_format="-%s"),
            transaction.orig_unit.encode('utf-8'),
            transaction.orig_organization.printable_name.encode('utf-8'),
            transaction.orig_account.encode('utf-8'),
            ('"%s"' % transaction.descr.replace(
                '\\', '\\\\').replace('"', '\"')).encode('utf-8')
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

    def queryrow_to_columns(self, transaction):
        return [
            transaction.created_at.date(),
            '{:.2f}'.format(
                (-1 if transaction.is_debit(self.organization) else 1) *
                # XXX integer division
                Decimal(transaction.dest_amount) / 100),
            transaction.dest_unit.encode('utf-8'),
            ('"%s"' % transaction.descr.replace(
                '\\', '\\\\').replace('"', '\"')).encode('utf-8')
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

    def queryrow_to_columns(self, transaction):
        return [
            transaction.created_at.date(),
            '{:.2f}'.format(
                (-1 if transaction.is_debit(self.organization) else 1) *
                # XXX integer division
                Decimal(transaction.dest_amount) / 100),
            transaction.dest_unit.encode('utf-8'),
            ('"%s"' % transaction.descr.replace(
                '\\', '\\\\').replace('"', '\"')).encode('utf-8')
        ]
