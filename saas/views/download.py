# Copyright (c) 2023, DjaoDjin inc.
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
from django.template.defaultfilters import slugify
from django.views.generic import View
from rest_framework.generics import get_object_or_404
from rest_framework.request import Request

from .. import humanize, settings
from ..api.balances import BrokerBalancesMixin
from ..api.charges import SmartChargeListMixin, ChargeQuerysetMixin
from ..api.coupons import CouponQuerysetMixin, SmartCouponListMixin
from ..api.metrics import (BalancesMetricsMixin, PlanMetricsMixin,
    RevenueMetricsMixin, CustomerMetricsMixin)
from ..api.organizations import (EngagedSubscribersQuerysetMixin,
    UnengagedSubscribersQuerysetMixin)
from ..api.serializers import OrganizationSerializer
from ..api.subscriptions import (ActiveSubscriberSubscriptionsMixin,
    ChurnedSubscribersMixin)
from ..api.transactions import (BillingsQuerysetMixin,
    SmartTransactionListMixin, TransactionQuerysetMixin, TransferQuerysetMixin)
from ..api.users import RegisteredQuerysetMixin
from ..compat import force_str, six, gettext_lazy as _
from ..metrics.base import month_periods
from ..mixins import (CartItemSmartListMixin, ProviderMixin,
    UserSmartListMixin, as_html_description, BalancesDueMixin,
    MetricsDownloadMixin)
from ..models import BalanceLine, CartItem, Coupon
from ..utils import datetime_or_now, convert_dates_to_utc


class CSVDownloadView(View):

    basename = 'download'
    headings = []
    filter_backends = []

    @staticmethod
    def encode(text):
        text_str = force_str(text)
        if hasattr(text_str, 'encode'):
            return text_str.encode('utf-8')
        return text_str

    def encode_descr(self, transaction):
        return self.encode(('"%s"' % as_html_description(transaction).replace(
            '\\', '\\\\').replace('"', '\"')))

    @staticmethod
    def decorate_queryset(queryset):
        return queryset

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
        qs = self.decorate_queryset(self.filter_queryset(self.get_queryset()))
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


class BalancesDownloadView(BrokerBalancesMixin, CSVDownloadView):
    """
    Export balance metrics as a CSV file.
    """
    queryname = 'balances'

    def get_headings(self):
        return ['Title'] + [str(end_period) for end_period in month_periods(
            from_date=self.ends_at, tzinfo=self.timezone)]

    def get_queryset(self):
        report = self.kwargs.get('report')
        return BalanceLine.objects.filter(report=report).order_by('rank')

    def queryrow_to_columns(self, record):
        balance_line = record
        date_periods = convert_dates_to_utc(month_periods(
            from_date=self.ends_at))
        if balance_line.selector:
            values, _unit = self.get_values(balance_line, date_periods)
            row = [balance_line.title] + [item[1] for item in values]
        else:
            # means we have a heading only
            row = [balance_line.title]
        return row


class ChargesDownloadView(SmartChargeListMixin, ChargeQuerysetMixin,
                          CSVDownloadView):
    """
    Export charges as a CSV file.
    """
    basename = 'charges'

    headings = [
        _('Created At'),
        _('Amount'),
        _('State'),
        _('Description'),
    ]

    def queryrow_to_columns(self, record):
        row = [
            record.created_at.date(),
            record.amount,
            record.state,
            record.description
        ]
        return row


class CouponDownloadView(SmartCouponListMixin, CouponQuerysetMixin,
                         CSVDownloadView):

    headings = [
        _('Created At'),
        _('Code'),
        _('DiscountType'),
        _('Amount'),
    ]

    def get_headings(self):
        return self.headings

    def get_filename(self):
        return datetime_or_now().strftime('coupons-%Y%m%d.csv')

    def queryrow_to_columns(self, record):
        row = [
            record.created_at.date(),
            record.code,
            record.get_discount_type_display(),
            record.discount_value
        ]
        return row


class CartItemQuerysetMixin(ProviderMixin):

    def get_queryset(self):
        return CartItem.objects.filter(coupon__organization=self.provider)


class CartItemDownloadView(CartItemSmartListMixin, CartItemQuerysetMixin,
                           CSVDownloadView):

    coupon_url_kwarg = 'coupon'

    headings = [
        _('Used At'),
        _('Code'),
        _('DiscountType'),
        _('Amount'),
        _('Name'),
        _('Email'),
        _('Plan'),
    ]

    @property
    def coupon_code(self):
        #pylint:disable=attribute-defined-outside-init
        if not hasattr(self, '_coupon_code'):
            self._coupon_code = self.kwargs.get(self.coupon_url_kwarg)
        return self._coupon_code

    def get_coupons(self):
        if self.coupon_code:
            coupon = get_object_or_404(
                Coupon.objects.filter(organization=self.provider),
                code=self.coupon_code)
            return [coupon]
        view = CouponDownloadView()
        #pylint:disable=attribute-defined-outside-init
        if hasattr(view, 'setup'):
            # `setup` is only defined in Django 2.2+
            view.setup(self.request, *self.args, **self.kwargs)
        else:
            view.request = self.request
            view.args = self.args
            view.kwargs = self.kwargs
        return view.get_queryset()

    def get_headings(self):
        return self.headings

    def get_filename(self):
        filename_tpl = ((self.coupon_code if self.coupon_code else 'coupons')
            + '-%Y%m%d.csv')
        return datetime_or_now().strftime(filename_tpl)

    def get_queryset(self):
        '''
        Return CartItems related to the Coupon specified in the URL.
        '''
        return super(CartItemDownloadView, self).get_queryset().filter(
            coupon__in=self.get_coupons())

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
            cartitem.created_at.date(),
            self.encode(cartitem.coupon.code),
            slugify(
                Coupon.DISCOUNT_CHOICES[cartitem.coupon.discount_type - 1][1]),
            cartitem.coupon.discount_value,
            self.encode(full_name),
            self.encode(email),
            self.encode(cartitem.plan.slug),
            self.encode(claim_code)]


class RegisteredDownloadView(UserSmartListMixin, RegisteredQuerysetMixin,
                             CSVDownloadView):

    def get_headings(self):
        return [_('First name'), _('Last name'), 'Email', _('Registration Date')]

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


class SubscriptionBaseDownloadView(CSVDownloadView):

    subscriber_type = None
    CSV_CUSTOMER_CONTACTS_INCLUDED = settings.CSV_CUSTOMER_CONTACTS_INCLUDED

    headings = [
        _('Name'),
        _('Email'),
        _('Plan'),
        _('Since'),
        _('Until')
    ]

    def get_queryset(self):
        raise NotImplementedError()

    def get_headings(self):
        if self.CSV_CUSTOMER_CONTACTS_INCLUDED:
            extra_headings = [
                _('Phone'),
                _('Street Address'),
                _('Locality'),
                _('Region'),
                _('Postal Code'),
                _('Country')
            ]
            self.headings += extra_headings
        return self.headings

    def get_filename(self):
        return 'subscribers-{}-{}.csv'.format(
            self.subscriber_type, datetime_or_now().strftime('%Y%m%d'))

    def queryrow_to_columns(self, record):
        subscription = record
        columns = [
            self.encode(subscription.organization.full_name),
            self.encode(subscription.organization.email),
            self.encode(subscription.plan.title),
            subscription.created_at.date(),
            subscription.ends_at.date(),
        ]

        if self.CSV_CUSTOMER_CONTACTS_INCLUDED:
            extra_columns = [
                self.encode(subscription.organization.phone),
                self.encode(subscription.organization.street_address),
                self.encode(subscription.organization.locality),
                self.encode(subscription.organization.region),
                self.encode(subscription.organization.postal_code),
                self.encode(subscription.organization.country)
            ]
            columns += extra_columns

        return columns


class ActiveSubscriptionDownloadView(ActiveSubscriberSubscriptionsMixin,
                                     SubscriptionBaseDownloadView):

    subscriber_type = 'active'


class ChurnedSubscriptionDownloadView(ChurnedSubscribersMixin,
                                      SubscriptionBaseDownloadView):

    subscriber_type = 'churned'


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
            self.encode_descr(transaction)
        ]


class BillingStatementDownloadView(SmartTransactionListMixin,
                           BillingsQuerysetMixin, CSVDownloadView):

    basename = 'history'
    headings = [
        _('Created At'),
        _('Amount'),
        _('Unit'),
        _('Description')
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
            self.encode_descr(transaction)
        ]


class TransferDownloadView(SmartTransactionListMixin,
                           TransferQuerysetMixin, CSVDownloadView):

    basename = 'transfers'
    CSV_CUSTOMER_CONTACTS_INCLUDED = settings.CSV_CUSTOMER_CONTACTS_INCLUDED

    headings = [
        _('Created At'),
        _('Amount'),
        _('Unit'),
        _('Description'),
        _('Full Name')
    ]

    def get_headings(self):
        if self.CSV_CUSTOMER_CONTACTS_INCLUDED:
            extra_headings = [
                _('Email'),
                _('Phone'),
                _('Street Address'),
                _('Locality'),
                _('Region'),
                _('Postal Code'),
                _('Country')
            ]
            self.headings += extra_headings
        return self.headings

    def queryrow_to_columns(self, record):
        transaction = record
        columns = [
            transaction.created_at.date(),
            '{:.2f}'.format(
                (-1 if transaction.is_debit(self.organization) else 1) *
                # XXX integer division
                Decimal(transaction.dest_amount) / 100),
            self.encode(transaction.dest_unit),
            self.encode_descr(transaction),
            self.encode(transaction.orig_organization.full_name)
        ]

        if self.CSV_CUSTOMER_CONTACTS_INCLUDED:
            organization = transaction.orig_organization
            extra_columns = [
                self.encode(organization.email),
                self.encode(organization.phone),
                self.encode(organization.street_address),
                self.encode(organization.locality),
                self.encode(organization.region),
                self.encode(organization.postal_code),
                self.encode(organization.country)
            ]
            columns += extra_columns

        return columns


class BalancesMetricsDownloadView(MetricsDownloadMixin, BalancesMetricsMixin,
                                  CSVDownloadView):
    basename = 'balancesmetrics'

    @property
    def metrics(self):
        if not hasattr(self, '_metrics'):
            #pylint:disable=attribute-defined-outside-init
            self._metrics, _ = self.get_data()
        return self._metrics

    def get_headings(self):
        return [''] + [val[0] for val in self.metrics[0]['values']]

    def queryrow_to_columns(self, record):
        row = [
            self.encode(record['title']),
        ]
        for val in record['values']:
            row.append(val[1])

        return row


class RevenueMetricsDownloadView(MetricsDownloadMixin, RevenueMetricsMixin,
                                 CSVDownloadView):

    basename = 'revenuemetrics'

    @property
    def metrics(self):
        if not hasattr(self, '_metrics'):
            #pylint:disable=attribute-defined-outside-init
            self._metrics, _ = self.get_data()
        return self._metrics

    def get_headings(self):
        return [''] + [val[0] for val in self.metrics[0]['values']]

    def queryrow_to_columns(self, record):
        row = [
            self.encode(record['title']),
        ]
        for val in record['values']:
            row.append(val[1])

        return row


class CustomerMetricsDownloadView(MetricsDownloadMixin, CustomerMetricsMixin,
                                  CSVDownloadView):

    basename = 'customermetrics'

    @property
    def metrics(self):
        if not hasattr(self, '_metrics'):
            #pylint:disable=attribute-defined-outside-init
            self._metrics, _ = self.get_data()
        return self._metrics

    def get_headings(self):
        return [''] + [val[0] for val in self.metrics[0]['values']]

    def queryrow_to_columns(self, record):
        row = [
            self.encode(record['title']),
        ]
        for val in record['values']:
            row.append(val[1])

        return row


class PlanMetricsDownloadView(MetricsDownloadMixin, PlanMetricsMixin,
                              CSVDownloadView):

    basename = 'planmetrics'

    @property
    def plans(self):
        if not hasattr(self, '_plans'):
            #pylint:disable=attribute-defined-outside-init
            self._plans, _ = self.get_data()
        return self._plans

    def get_headings(self):
        return [''] + [val[0] for val in self.plans[0]['values']]

    def queryrow_to_columns(self, record):
        row = [
            self.encode(record['title']),
        ]
        for val in record['values']:
            row.append(val[1])

        return row


class BalancesDueDownloadView(BalancesDueMixin, CSVDownloadView):

    basename = 'balances_due'

    def get_headings(self):
        basic_headers = [
            _('Slug'),
            _('Profile Name'),
            _('Created At')
        ]

        currency_set = self.currency_set
        currency_headers = []
        for currency in currency_set:
            for balance_type in ['contract_value', 'cash_payments', 'balance']:
                currency_headers += ["%s_%s" % (currency, balance_type)]

        return basic_headers + currency_headers

    @property
    def currency_set(self):
        if not hasattr(self, '_currency_set'):
            currency_set = set()
            for balances in self.balances_due.values():
                currency_set.update(balances.keys())
            #pylint:disable=attribute-defined-outside-init
            self._currency_set = currency_set

        return self._currency_set

    def queryrow_to_columns(self, record):
        organization_balances = self.balances_due.get(record.slug, {})
        row = [
            self.encode(getattr(record, 'slug', '')),
            self.encode(getattr(record, 'printable_name', '')),
            self.encode(getattr(record, 'created_at', ''))
        ]

        for currency in self.currency_set:
            balances = organization_balances.get(currency, {})
            row.extend([self.encode(balances.get(key, 0)) for key in
                        ['contract_value', 'cash_payments', 'balance']])

        return row


class EngagedSubscribersDownloadView(EngagedSubscribersQuerysetMixin, CSVDownloadView):

    basename = 'engaged_subscribers'

    headings = [
        _('Created At'),
        _('Username'),
        _('Email'),
        _('Full Name'),
        _('Account Creation Date'),
        _('Role Description'),
        _('Profile Slug'),
        _('Profile Name'),
        _('Profile Creation Date')
    ]

    def queryrow_to_columns(self, record):
        user = record.user
        role_description = record.role_description
        organization = record.organization

        return [
            self.encode(getattr(record, 'created_at', '')),
            self.encode(getattr(user, 'username', '')),
            self.encode(getattr(user, 'email', '')),
            self.encode(getattr(user, 'get_full_name', '')()),
            self.encode(getattr(user, 'date_joined', '')),
            self.encode(getattr(role_description, 'title', '')),
            self.encode(getattr(organization, 'slug', '')),
            self.encode(getattr(organization, 'printable_name', '')),
            self.encode(getattr(organization, 'created_at', '')),
        ]


class UnengagedSubscribersDownloadView(UnengagedSubscribersQuerysetMixin, CSVDownloadView):

    basename = 'unengaged_subscribers'

    headings = [
        _('Slug'),
        _('Profile Name'),
        _('Type'),
        _('Credentials'),
        _('Created At')
    ]

    def queryrow_to_columns(self, record):
        record = OrganizationSerializer(record).data
        return [
            self.encode(record['printable_name']) if
            heading == 'Profile Name' else
            self.encode(record.get('_'.join(heading.lower().split()), ''))
            for heading in self.get_headings()
        ]
