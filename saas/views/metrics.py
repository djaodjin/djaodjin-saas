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

import json
from datetime import datetime

from django.views.generic import TemplateView

from .. import settings
from ..compat import reverse
from ..mixins import CouponMixin, ProviderMixin, MetricsMixin
from ..models import CartItem, Plan
from ..utils import datetime_or_now, update_context_urls


class BalancesView(ProviderMixin, TemplateView):
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
        context = super(BalancesView, self).get_context_data(**kwargs)
        report = self.kwargs.get('report')
        year = self.kwargs.get('year')
        if year:
            year = int(year)
            ends_at = datetime_or_now(datetime(year=year + 1, month=1, day=1))
            context.update({'ends_at': ends_at})
        update_context_urls(context, {
            'api_balance_lines': reverse(
                'saas_api_balance_lines', kwargs={'report': report}),
            'api_broker_balances': reverse(
                'saas_api_broker_balances', kwargs={'report': report}),
            'download_balances': reverse(
                'saas_balances_download', kwargs={'report': report}),
            'download_transactions': reverse(
                'saas_transactions_download', kwargs=self.get_url_kwargs()),
            'broker_transactions': reverse('saas_broker_transactions')})
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
        update_context_urls(context, urls)
        return context


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
    ``saas/metrics/revenue.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/metrics/revenue.html>`__).

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

    template_name = 'saas/metrics/revenue.html'

    def get_context_data(self, **kwargs):
        context = super(RevenueMetricsView, self).get_context_data(**kwargs)
        unit = settings.DEFAULT_UNIT
        a_receivable = self.organization.receivables().first()
        if a_receivable:
            unit = a_receivable.orig_unit
        context.update({
            "title": "Sales",
            "tables": json.dumps(
                [{"key": "cash",
                        "title": "Amounts",
                        "unit": unit,
                        "location": reverse('saas_api_revenue',
                            args=(self.organization,))},
                       {"key": "customer",
                        "title": "Customers",
                        "location": reverse('saas_api_customer',
                            args=(self.organization,))},
                       {"key": "balances",
                        "title": "Balances",
                        "unit": unit,
                        "location": reverse('saas_api_balances',
                            args=(self.organization,))}])})
        return context
