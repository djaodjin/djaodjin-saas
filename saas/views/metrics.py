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

import json
from datetime import datetime

from django.core.urlresolvers import reverse
from django.views.generic import TemplateView

from .download import CSVDownloadView
from ..api.coupons import SmartCouponListMixin, CouponQuerysetMixin
from ..api.users import RegisteredQuerysetMixin
from ..managers.metrics import monthly_balances, month_periods
from ..mixins import (CouponMixin, ProviderMixin, MetricsMixin,
    ChurnedQuerysetMixin, SubscriptionSmartListMixin, SubscribedQuerysetMixin,
    UserSmartListMixin)
from ..models import CartItem, Plan, Transaction
from ..utils import datetime_or_now


class BalanceView(ProviderMixin, TemplateView):
    """
    Display a balance sheet named ``:report``.

    Template:

    To edit the layout of this page, create a local \
    ``saas/metrics/balances.html`` (`example <https://github.com/djaodjin/\
djaodjin-saas/tree/master/saas/templates/saas/metrics/balances.html>`__).

    Template context:
      - ``organization`` The provider object
      - ``request`` The HTTP request object
    """

    template_name = 'saas/metrics/balances.html'

    def get_context_data(self, **kwargs):
        context = super(BalanceView, self).get_context_data(**kwargs)
        report = self.kwargs.get('report')
        year = self.kwargs.get('year')
        if year:
            year = int(year)
            ends_at = datetime_or_now(datetime(year=year + 1, month=1, day=1))
            context.update({'ends_at': ends_at.isoformat()})
        urls = {
            'api_balance_lines': reverse(
                'saas_api_balance_lines', kwargs={'report': report}),
            'api_broker_balances': reverse(
                'saas_api_broker_balances', kwargs={'report': report}),
            'download_transactions': reverse(
                'saas_transactions_download', kwargs=self.get_url_kwargs())}
        if 'urls' in context:
            context['urls'].update(urls)
        else:
            context.update({'urls': urls})
        return context


class CouponMetricsView(CouponMixin, TemplateView):
    """
    Performance of Coupon based on CartItem.

    Template:

    To edit the layout of this page, create a local \
    ``saas/metrics/coupons.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/metrics/coupons.html>`__).

    Template context:
      - ``coupon`` The coupon the list of uses refers to
      - ``organization`` The provider object
      - ``request`` The HTTP request object
    """

    model = CartItem
    template_name = 'saas/metrics/coupons.html'

    def get_context_data(self, **kwargs):
        context = super(CouponMetricsView, self).get_context_data(**kwargs)
        urls = {'provider': {
            'api_metrics_coupon_uses': reverse(
                'saas_api_coupon_uses',
                args=(self.provider, self.coupon.code))}}
        if 'urls' in context:
            for key, val in urls.iteritems():
                if key in context['urls']:
                    context['urls'][key].update(val)
                else:
                    context['urls'].update({key: val})
        else:
            context.update({'urls': urls})
        return context


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
        return datetime.now().strftime('coupons-%Y%m%d.csv')

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


class PlansMetricsView(ProviderMixin, TemplateView):
    """
    Performance of Plans for a time period
    (as a count of subscribers per plan per month)

    Template:

    To edit the layout of this page, create a local \
    ``saas/metrics/plans.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/metrics/plans.html>`__).
    The page will typically call back
    :ref:`/api/metrics/:organization/plans/ <api_metrics_plans>`
    to fetch the 12 month trailing performance in terms of subscribers
    of the plans of a provider.

    Template context:
      - ``organization`` The provider object
      - ``request`` The HTTP request object
    """

    template_name = 'saas/metrics/plans.html'

    def get_context_data(self, **kwargs):
        context = super(PlansMetricsView, self).get_context_data(**kwargs)
        context.update({
            "title": "Plans",
            "tables" : json.dumps([{
                "title": "Active subscribers",
                "key": "plan",
                "active": True,
                "location": reverse(
                    'saas_api_metrics_plans', args=(self.provider,))},
            ]),
            "plans": Plan.objects.filter(organization=self.provider)})
        urls_provider = {
            'plan_new': reverse('saas_plan_new', args=(self.provider,))}
        if 'urls' in context:
            if 'provider' in context['urls']:
                context['urls']['provider'].update(urls_provider)
            else:
                context['urls'].update({'provider': urls_provider})
        else:
            context.update({'urls': {'provider': urls_provider}})
        return context


class RevenueMetricsView(MetricsMixin, TemplateView):
    """
    Reports cash flow and revenue in currency units.

    Template:

    To edit the layout of this page, create a local \
    ``saas/metrics/base.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/metrics/base.html>`__).

    The page will typically call back
    :ref:`/api/metrics/:organization/funds/ <api_metrics_funds>`
    to fetch the 12 month trailing cash flow table, and/or
    :ref:`/api/metrics/:organization/balances/ <api_metrics_balances>`
    to fetch the 12 month trailing receivable/backlog/income revenue.

    The example page also calls back
    :ref:`/api/metrics/:organization/customers/ <api_metrics_customers>`
    to fetch the distinct number of customers that generated the cash
    transactions.

    Template context:
      - ``organization`` The provider object
      - ``request`` The HTTP request object
    """

    template_name = 'saas/metrics/base.html'

    def get_context_data(self, **kwargs):
        context = super(RevenueMetricsView, self).get_context_data(**kwargs)
        context.update({
            "title": "Sales",
            "tables": json.dumps(
                [{"key": "cash",
                        "title": "Amounts",
                        "unit": "$",
                        "location": reverse('saas_api_revenue',
                            args=(self.organization,))},
                       {"key": "customer",
                        "title": "Customers",
                        "location": reverse('saas_api_customer',
                            args=(self.organization,))},
                       {"key": "balances",
                        "title": "Balances",
                        "unit": "$",
                        "location": reverse('saas_api_balances',
                            args=(self.organization,))}])})
        return context


class BalancesDownloadView(MetricsMixin, CSVDownloadView):
    """
    Export balance metrics as a CSV file.
    """
    queryname = 'balances'

    def get_headings(self):
        return ['name'] + [
            end_period for end_period in month_periods(from_date=self.ends_at)]

    def get_filename(self, *_):
        return '{}.csv'.format(self.queryname)

    def get_queryset(self, *_):
        return Transaction.objects.distinct_accounts()

    def queryrow_to_columns(self, account):
        return [account] + [item[1] for item in monthly_balances(
            organization=self.organization, account=account,
            until=self.ends_at.date())]


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
