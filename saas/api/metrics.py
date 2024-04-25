# Copyright (c) 2024, DjaoDjin inc.
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

import logging

from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response

from .serializers import (CartItemSerializer, LifetimeSerializer,
    MetricsSerializer, QueryParamPeriodSerializer, BalancesDueSerializer)
from .. import settings, humanize
from ..compat import gettext_lazy as _, reverse, six
from ..docs import extend_schema
from ..filters import DateRangeFilter, OrderingFilter, SearchFilter
from ..metrics.base import (abs_balances_by_period,
    aggregate_transactions_by_period, aggregate_transactions_change_by_period,
    generate_periods, get_different_units)
from ..metrics.subscriptions import (active_subscribers_by_period,
    churn_subscribers_by_period, subscribers_age)
from ..metrics.transactions import lifetime_value
from ..mixins import (CartItemSmartListMixin, CouponMixin,
    ProviderMixin, DateRangeContextMixin, BalancesDueMixin)
from ..models import CartItem, Plan, Transaction
from ..utils import convert_dates_to_utc, get_organization_model

LOGGER = logging.getLogger(__name__)


class MetricsMixin(DateRangeContextMixin, ProviderMixin):
    """
    Base class for metrics APIs
    """
    period_type_param = 'period_type'
    nb_periods_param = 'nb_periods'
    serializer_class = MetricsSerializer

    def calculate_date_periods(self):
        # We use self.get_query_param since this Mixin is also used
        # by the CSVDownloadViews, which sends in a Django request instead
        # of a DRF request
        nb_periods = self.get_query_param(self.nb_periods_param)
        period_type = self.get_query_param(self.period_type_param)

        query_params = {}
        if nb_periods:
            query_params[self.nb_periods_param] = nb_periods
        if period_type:
            query_params[self.period_type_param] = period_type

        query_serializer = QueryParamPeriodSerializer(data=query_params)
        query_serializer.is_valid(raise_exception=True)

        nb_periods = query_serializer.validated_data.get(
            self.nb_periods_param)
        period_type = query_serializer.validated_data.get(
            self.period_type_param, humanize.MONTHLY)

        date_periods = convert_dates_to_utc(
            generate_periods(period_type, nb_periods=nb_periods,
                             from_date=self.ends_at,
                             tzinfo=self.organization.default_timezone))

        return date_periods


class BalancesMetricsMixin(MetricsMixin):

    def get_data(self):
        results = []

        date_periods = self.calculate_date_periods()
        unit = settings.DEFAULT_UNIT
        for key in [Transaction.INCOME, Transaction.BACKLOG,
                    Transaction.RECEIVABLE]:
            values, _unit = abs_balances_by_period(
                organization=self.provider, account=key,
                date_periods=date_periods)

            if _unit:
                unit = _unit

            results += [{
                'slug': key,
                'title': key,
                'values': values
            }]

        return results, unit

    def retrieve_metrics(self):
        results, unit = self.get_data()

        return Response({
            'title': "Balances",
            'unit': unit,
            'scale': 0.01,
            'results': results
        })


class RevenueMetricsMixin(MetricsMixin):

    def get_data(self):
        unit = settings.DEFAULT_UNIT

        date_periods = self.calculate_date_periods()

        account_table, _, _, table_unit = \
            aggregate_transactions_change_by_period(self.provider,
                Transaction.RECEIVABLE, account_title='Sales',
                orig='orig', dest='dest',
                date_periods=date_periods)

        _, payment_amounts, payments_unit = aggregate_transactions_by_period(
            self.provider, Transaction.RECEIVABLE,
            orig='dest', dest='dest',
            orig_account=Transaction.BACKLOG,
            orig_organization=self.provider,
            date_periods=date_periods)

        _, refund_amounts, refund_unit = aggregate_transactions_by_period(
            self.provider, Transaction.REFUND,
            orig='dest', dest='dest',
            date_periods=date_periods)

        units = get_different_units(table_unit, payments_unit, refund_unit)

        if len(units) > 1:
            LOGGER.error("different units in RevenueMetricAPIView.get: %s",
                units)

        if units:
            unit = units[0]

        account_table += [{
            'slug': "payments",
            'title': "Payments",
            'values': payment_amounts
        }, {
            'slug': "refunds",
            'title': "Refunds",
            'values': refund_amounts
        }]

        return account_table, unit

    def retrieve_metrics(self):
        account_table, unit = self.get_data()
        resp = {
            'title': "Amount",
            'unit': unit,
            'scale': 0.01,
            'results': account_table
        }
        if not self.provider.has_bank_account:
            resp.update({'processor_hint': 'connect_provider'})

        return Response(resp)


class CustomerMetricsMixin(MetricsMixin):

    def get_data(self):
        account_title = 'Payments'
        account = Transaction.RECEIVABLE
        # We use ``Transaction.RECEIVABLE`` which technically counts the number
        # or orders, not the number of payments.
        date_periods = self.calculate_date_periods()
        _, customer_table, customer_extra, _ = \
            aggregate_transactions_change_by_period(self.provider, account,
                account_title=account_title,
                date_periods=date_periods)
        return customer_table, customer_extra

    def retrieve_metrics(self):
        customer_table, customer_extra = self.get_data()
        return Response({
            "title": "Customers",
            "results": customer_table,
            "extra": customer_extra
        })


class PlanMetricsMixin(MetricsMixin):

    def get_data(self):
        table = []
        date_periods = self.calculate_date_periods()
        for plan in Plan.objects.filter(
                organization=self.provider).order_by('title'):
            values = active_subscribers_by_period(
                plan, date_periods=date_periods)
            table.append({
                'slug': plan.slug,
                'title': plan.title,
                'location': reverse('saas_plan_edit', args=(
                    self.provider, plan)),
                'is_active': plan.is_active,
                'values': values,
            })

        extra_values = churn_subscribers_by_period(date_periods=date_periods)
        extra = [{
            'slug': 'churn',
            'values': extra_values
        }]
        return table, extra

    def retrieve_metrics(self):

        table, extra = self.get_data()

        return Response({
            'title': _("Active subscribers"),
            'results': table,
            'extra': extra
        })


class BalancesAPIView(BalancesMetricsMixin, GenericAPIView):
    """
    Retrieves trailing deferred balances

    Generates a table of currency amounts (rows) per period (columns)
    for a default balance sheet (Income, Backlog, Receivable).

    The date/time returned in `results[].values[]` specifies the end
    of the period (not included) for which the associated amount
    in the tuple is computed.

    The date from which trailing balances are computed can be specified
    by the `ends_at` query parameter. The type of periods (hourly, daily,
    weekly, monthly, yearly) to aggregate balances over, and the number of
    periods to return can be specificed by `period_type` and `nb_periods`
    respectively.

    The API is typically used within an HTML
    `revenue page </docs/guides/themes/#dashboard_metrics_revenue>`_
    as present in the default theme.

    **Tags**: chart, metrics, provider, transactionmodel

    **Examples**

    .. code-block:: http

        GET /api/metrics/cowork/balances HTTP/1.1

    responds

    .. code-block:: json

        {
            "title": "Balances",
            "scale": 0.01,
            "unit": "usd",
            "results": [
                {
                    "slug": "income",
                    "title": "Income",
                    "values": [
                        ["2014-09-01T00:00:00Z", 0],
                        ["2014-10-01T00:00:00Z", 1532624],
                        ["2014-11-01T00:00:00Z", 2348340],
                        ["2014-12-01T00:00:00Z", 3244770],
                        ["2015-01-01T00:00:00Z", 5494221],
                        ["2015-02-01T00:00:00Z", 7214221],
                        ["2015-03-01T00:00:00Z", 8444221],
                        ["2015-04-01T00:00:00Z", 9784221],
                        ["2015-05-01T00:00:00Z", 12784221],
                        ["2015-06-01T00:00:00Z", 14562341],
                        ["2015-07-01T00:00:00Z", 16567341],
                        ["2015-08-01T00:00:00Z", 17893214],
                        ["2015-08-06T02:24:50.485Z", 221340]
                    ]
                },
                {
                    "slug": "backlog",
                    "title": "Backlog",
                    "values": [
                        ["2014-09-01T00:00:00Z", 1712624],
                        ["2014-10-01T00:00:00Z", 3698340],
                        ["2014-11-01T00:00:00Z", 7214770],
                        ["2014-12-01T00:00:00Z", 10494221],
                        ["2015-01-01T00:00:00Z", 14281970],
                        ["2015-02-01T00:00:00Z", 18762845],
                        ["2015-03-01T00:00:00Z", 24258765],
                        ["2015-04-01T00:00:00Z", 31937741],
                        ["2015-05-01T00:00:00Z", 43002401],
                        ["2015-06-01T00:00:00Z", 53331444],
                        ["2015-07-01T00:00:00Z", 64775621],
                        ["2015-08-01T00:00:00Z", 75050033],
                        ["2015-08-06T02:24:50.485Z", 89156321]
                    ]
                },
                {
                    "slug": "Receivable",
                    "title": "Receivable",
                    "values": [
                        ["2014-09-01T00:00:00Z", 0],
                        ["2014-10-01T00:00:00Z", 0],
                        ["2014-11-01T00:00:00Z", 0],
                        ["2014-12-01T00:00:00Z", 0],
                        ["2015-01-01T00:00:00Z", 0],
                        ["2015-02-01T00:00:00Z", 0],
                        ["2015-03-01T00:00:00Z", 0],
                        ["2015-04-01T00:00:00Z", 0],
                        ["2015-05-01T00:00:00Z", 0],
                        ["2015-06-01T00:00:00Z", 0],
                        ["2015-07-01T00:00:00Z", 0],
                        ["2015-08-01T00:00:00Z", 0],
                        ["2015-08-06T02:24:50.485Z", 0]
                    ]
                }
            ]
        }
    """

    @extend_schema(parameters=[QueryParamPeriodSerializer])
    def get(self, request, *args, **kwargs):
        return self.retrieve_metrics()


class RevenueMetricAPIView(RevenueMetricsMixin, GenericAPIView):
    """
    Retrieves trailing revenue

    Produces sales, payments and refunds over a period of time.

    The API is typically used within an HTML
    `revenue page </docs/guides/themes/#dashboard_metrics_revenue>`_
    as present in the default theme.

    **Tags**: chart, metrics, provider, transactionmodel

    **Examples**

    .. code-block:: http

        GET /api/metrics/cowork/funds HTTP/1.1

    responds

    .. code-block:: json

        {
            "title": "Amount",
            "scale": 0.01,
            "unit": "usd",
            "results": [
                {
                    "slug": "total-sales",
                    "title": "Total Sales",
                    "values": [
                        ["2014-10-01T00:00:00Z", 1985716],
                        ["2014-11-01T00:00:00Z", 3516430],
                        ["2014-12-01T00:00:00Z", 3279451],
                        ["2015-01-01T00:00:00Z", 3787749],
                        ["2015-02-01T00:00:00Z", 4480875],
                        ["2015-03-01T00:00:00Z", 5495920],
                        ["2015-04-01T00:00:00Z", 7678976],
                        ["2015-05-01T00:00:00Z", 11064660],
                        ["2015-06-01T00:00:00Z", 10329043],
                        ["2015-07-01T00:00:00Z", 11444177],
                        ["2015-08-01T00:00:00Z", 10274412],
                        ["2015-08-06T04:59:14.721Z", 14106288]
                    ]
                },
                {
                    "slug": "new-sales",
                    "title": "New Sales",
                    "values": [
                        ["2014-10-01T00:00:00Z", 0],
                        ["2014-11-01T00:00:00Z", 0],
                        ["2014-12-01T00:00:00Z", 0],
                        ["2015-01-01T00:00:00Z", 0],
                        ["2015-02-01T00:00:00Z", 0],
                        ["2015-03-01T00:00:00Z", 0],
                        ["2015-04-01T00:00:00Z", 0],
                        ["2015-05-01T00:00:00Z", 0],
                        ["2015-06-01T00:00:00Z", 0],
                        ["2015-07-01T00:00:00Z", 0],
                        ["2015-08-01T00:00:00Z", 0],
                        ["2015-08-06T04:59:14.721Z", 0]
                    ]
                },
                {
                    "slug": "churned-sales",
                    "title": "Churned Sales",
                    "values": [
                        ["2014-10-01T00:00:00Z", 0],
                        ["2014-11-01T00:00:00Z", 0],
                        ["2014-12-01T00:00:00Z", 0],
                        ["2015-01-01T00:00:00Z", 0],
                        ["2015-02-01T00:00:00Z", 0],
                        ["2015-03-01T00:00:00Z", 0],
                        ["2015-04-01T00:00:00Z", 0],
                        ["2015-05-01T00:00:00Z", 0],
                        ["2015-06-01T00:00:00Z", 0],
                        ["2015-07-01T00:00:00Z", 0],
                        ["2015-08-01T00:00:00Z", 0],
                        ["2015-08-06T04:59:14.721Z", 0]
                    ]
                },
                {
                    "slug": "payments",
                    "title": "Payments",
                    "values": [
                        ["2014-10-01T00:00:00Z", 1787144],
                        ["2014-11-01T00:00:00Z", 3164787],
                        ["2014-12-01T00:00:00Z", 2951505],
                        ["2015-01-01T00:00:00Z", 3408974],
                        ["2015-02-01T00:00:00Z", 4032787],
                        ["2015-03-01T00:00:00Z", 4946328],
                        ["2015-04-01T00:00:00Z", 6911079],
                        ["2015-05-01T00:00:00Z", 9958194],
                        ["2015-06-01T00:00:00Z", 9296138],
                        ["2015-07-01T00:00:00Z", 10299759],
                        ["2015-08-01T00:00:00Z", 9246970],
                        ["2015-08-06T04:59:14.721Z", 12695659]
                    ]
                },
                {
                    "slug": "refunds",
                    "title": "Refunds",
                    "values": [
                        ["2014-10-01T00:00:00Z", 0],
                        ["2014-11-01T00:00:00Z", 0],
                        ["2014-12-01T00:00:00Z", 0],
                        ["2015-01-01T00:00:00Z", 0],
                        ["2015-02-01T00:00:00Z", 0],
                        ["2015-03-01T00:00:00Z", 0],
                        ["2015-04-01T00:00:00Z", 0],
                        ["2015-05-01T00:00:00Z", 0],
                        ["2015-06-01T00:00:00Z", 0],
                        ["2015-07-01T00:00:00Z", 0],
                        ["2015-08-01T00:00:00Z", 0],
                        ["2015-08-06T04:59:14.721Z", 0]
                    ]
                }
            ]
        }
    """

    @extend_schema(parameters=[QueryParamPeriodSerializer])
    def get(self, request, *args, **kwargs):
        return self.retrieve_metrics()


class CouponUsesQuerysetMixin(object):

    def get_queryset(self):
        return CartItem.objects.filter(coupon=self.coupon, recorded=True)


class CouponUsesAPIView(CartItemSmartListMixin, CouponUsesQuerysetMixin,
                        CouponMixin, ListAPIView):
    """
    Retrieves performance of a discount code

    Returns a list of {{PAGE_SIZE}} cart items on which coupon with
    code {coupon} was used. Coupon {coupon} must have been created by
    the specified provider.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    **Tags**: metrics, list, provider, couponmodel

    **Examples**

    .. code-block:: http

        GET /api/metrics/cowork/coupons/DIS100 HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "user": {
                        "slug": "xia",
                        "username": "xia",
                        "title": "Xia Lee",
                        "picture": null
                    },
                    "plan": {
                      "slug": "basic",
                      "title": "Basic"
                    },
                    "created_at": "2014-01-01T09:00:00Z"
                }
            ]
        }
    """
    forced_date_range = False
    serializer_class = CartItemSerializer


class CustomerMetricAPIView(CustomerMetricsMixin, GenericAPIView):
    """
    Retrieves trailing customer counts

    Generates a table of total number of customers, number of new customers,
    number of churned customers, and number of net new customers (rows)
    per period (columns).

    New customers are defined as customers that made an order in the period,
    but not in the previous period. Churned customers are defined as customers
    that made an order in the previous period, but not in the period.
    The net new customers is defined as the number of new customers minus
    the number of churned customers.

    The date/time returned in `results[].values[]` specifies the end
    of the period (not included) for which the associated count
    in the tuple is computed.

    The date from which trailing balances are computed can be specified
    by the `ends_at` query parameter. The type of periods (hourly, daily,
    weekly, monthly, yearly) to aggregate balances over, and the number of
    periods to return can be specificed by `period_type` and `nb_periods`
    respectively.

    The API is typically used within an HTML
    `revenue page </docs/guides/themes/#dashboard_metrics_revenue>`_
    as present in the default theme.

    **Tags**: chart, metrics, provider, profilemodel

    **Examples**

    .. code-block:: http

        GET /api/metrics/cowork/customers HTTP/1.1

    responds

    .. code-block:: json

        {
            "title": "Customers",
            "results": [
                {
                    "slug": "total-customers",
                    "title": "Total # of Customers",
                    "values": [
                        ["2014-10-01T00:00:00Z", 15],
                        ["2014-11-01T00:00:00Z", 17],
                        ["2014-12-01T00:00:00Z", 19],
                        ["2015-01-01T00:00:00Z", 19],
                        ["2015-02-01T00:00:00Z", 25],
                        ["2015-03-01T00:00:00Z", 29],
                        ["2015-04-01T00:00:00Z", 37],
                        ["2015-05-01T00:00:00Z", 43],
                        ["2015-06-01T00:00:00Z", 46],
                        ["2015-07-01T00:00:00Z", 48],
                        ["2015-08-01T00:00:00Z", 54],
                        ["2015-08-06T05:20:24.537Z", 60]
                    ]
                },
                {
                    "slug": "new-customers",
                    "title": "# of new Customers",
                    "values": [
                        ["2014-10-01T00:00:00Z", 2],
                        ["2014-11-01T00:00:00Z", 2],
                        ["2014-12-01T00:00:00Z", 0],
                        ["2015-01-01T00:00:00Z", 6],
                        ["2015-02-01T00:00:00Z", 4],
                        ["2015-03-01T00:00:00Z", 8],
                        ["2015-04-01T00:00:00Z", 6],
                        ["2015-05-01T00:00:00Z", 3],
                        ["2015-06-01T00:00:00Z", 2],
                        ["2015-07-01T00:00:00Z", 6],
                        ["2015-08-01T00:00:00Z", 7],
                        ["2015-08-06T05:20:24.537Z", 0]
                    ]
                },
                {
                    "slug": "churned-customers",
                    "title": "# of churned Customers",
                    "values": [
                        ["2014-10-01T00:00:00Z", 0],
                        ["2014-11-01T00:00:00Z", 0],
                        ["2014-12-01T00:00:00Z", 0],
                        ["2015-01-01T00:00:00Z", 0],
                        ["2015-02-01T00:00:00Z", 0],
                        ["2015-03-01T00:00:00Z", 0],
                        ["2015-04-01T00:00:00Z", 0],
                        ["2015-05-01T00:00:00Z", 0],
                        ["2015-06-01T00:00:00Z", 0],
                        ["2015-07-01T00:00:00Z", 0],
                        ["2015-08-01T00:00:00Z", 1],
                        ["2015-08-06T05:20:24.537Z", 60]
                    ]
                },
                {
                    "slug": "net-new-customers",
                    "title": "Net New Customers",
                    "values": [
                        ["2014-10-01T00:00:00Z", 2],
                        ["2014-11-01T00:00:00Z", 2],
                        ["2014-12-01T00:00:00Z", 0],
                        ["2015-01-01T00:00:00Z", 6],
                        ["2015-02-01T00:00:00Z", 4],
                        ["2015-03-01T00:00:00Z", 8],
                        ["2015-04-01T00:00:00Z", 6],
                        ["2015-05-01T00:00:00Z", 3],
                        ["2015-06-01T00:00:00Z", 2],
                        ["2015-07-01T00:00:00Z", 6],
                        ["2015-08-01T00:00:00Z", 6],
                        ["2015-08-06T05:20:24.537Z", -60]
                    ]
                }
            ]
        }
    """

    @extend_schema(parameters=[QueryParamPeriodSerializer])
    def get(self, request, *args, **kwargs):
        return self.retrieve_metrics()


class LifetimeValueMetricMixin(DateRangeContextMixin, ProviderMixin):
    """
    Decorates profiles with subscriber age and lifetime value
    """
    search_fields = (
        'slug',
        'full_name',
    )

    ordering_fields = (
        ('slug', 'slug'),
        ('full_name', 'full_name'),
        ('created_at', 'created_at')
    )
    ordering = ('-created_at',)

    filter_backends = (DateRangeFilter, SearchFilter, OrderingFilter)

    def get_queryset(self):
        organization_model = get_organization_model()
        if self.provider:
            queryset = organization_model.objects.filter(
                subscribes_to__organization=self.provider).distinct()
        else:
            queryset = organization_model.objects.all()
        queryset = queryset.filter(
            outgoing__orig_account=Transaction.PAYABLE).distinct()
        return queryset

    def decorate_queryset(self, queryset):
        decorated_queryset = list(queryset)
        subscriber_ages = {subscriber['slug']: subscriber
            for subscriber in subscribers_age(provider=self.provider)}
        customer_values = lifetime_value(provider=self.provider)
        for organization in decorated_queryset:
            subscriber = subscriber_ages.get(organization.slug)
            if subscriber:
                organization.created_at = subscriber['created_at']
                organization.ends_at = subscriber['ends_at']
            else:
                organization.ends_at = None
            customer = customer_values.get(organization.slug)
            if customer:
                for unit, val in six.iteritems(customer):
                    # XXX Only supports one currency unit.
                    organization.unit = unit
                    organization.contract_value = val['contract_value']
                    organization.cash_payments = val['payments']
                    organization.deferred_revenue = val['deferred_revenue']
            else:
                organization.unit = settings.DEFAULT_UNIT
                organization.contract_value = 0
                organization.cash_payments = 0
                organization.deferred_revenue = 0
        return decorated_queryset


class LifetimeValueMetricAPIView(LifetimeValueMetricMixin, ListAPIView):
    """
    Retrieves customers lifetime value

    Generates the total amount of the contract for a customer,
    the amount of cash payments towards the contract value made so far
    by the customer, and the deferred revenue remaining to be recognized
    on the contract value.

    **Tags**: metrics, list, provider, profilemodel

    **Examples**

    .. code-block:: http

        GET /api/metrics/cowork/lifetimevalue HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "slug": "xia",
                    "title": "Xia Lee",
                    "picture": null,
                    "type": "personal",
                    "credentials": true,
                    "created_at": "2014-01-01T09:00:00Z",
                    "ends_at": "2014-01-01T09:00:00Z",
                    "unit": "usd",
                    "contract_value": 10000,
                    "cash_payments": 10000,
                    "deferred_revenue": 10000
                }
            ]
        }
    """
    serializer_class = LifetimeSerializer

    def paginate_queryset(self, queryset):
        page = super(
            LifetimeValueMetricAPIView, self).paginate_queryset(queryset)
        return self.decorate_queryset(page if page else queryset)


class PlanMetricAPIView(PlanMetricsMixin, GenericAPIView):
    """
    Retrieves trailing plans performance

    Generates a table of active susbribers for each plan (rows)
    per period (columns).

    The date/time returned in `results[].values[]` specifies the end
    of the period (not included) for which the associated count
    in the tuple is computed.

    The date from which trailing balances are computed can be specified
    by the `ends_at` query parameter. The type of periods (hourly, daily,
    weekly, monthly, yearly) to aggregate balances over, and the number of
    periods to return can be specificed by `period_type` and `nb_periods`
    respectively.

    The API is typically used within an HTML
    `revenue page </docs/guides/themes/#dashboard_metrics_revenue>`_
    as present in the default theme.

    **Tags**: chart, metrics, provider, planmodel

    **Examples**

    .. code-block:: http

        GET /api/metrics/cowork/plans HTTP/1.1

    responds

    .. code-block:: json

        {
            "title": "Active Subscribers",
            "results": [
                {
                    "is_active": true,
                    "slug": "open-space",
                    "title": "Open Space",
                    "location": "/profile/plan/open-space/",
                    "values": [
                        ["2014-09-01T00:00:00Z", 4],
                        ["2014-10-01T00:00:00Z", 5],
                        ["2014-11-01T00:00:00Z", 6],
                        ["2014-12-01T00:00:00Z", 6],
                        ["2015-01-01T00:00:00Z", 6],
                        ["2015-02-01T00:00:00Z", 9],
                        ["2015-03-01T00:00:00Z", 9],
                        ["2015-04-01T00:00:00Z", 9],
                        ["2015-05-01T00:00:00Z", 11],
                        ["2015-06-01T00:00:00Z", 11],
                        ["2015-07-01T00:00:00Z", 14],
                        ["2015-08-01T00:00:00Z", 16],
                        ["2015-08-06T05:37:50.004Z", 16]
                    ]
                },
                {
                    "is_active": true,
                    "slug": "open-plus",
                    "title": "Open Plus",
                    "location": "/profile/plan/open-plus/",
                    "values": [
                        ["2014-09-01T00:00:00Z", 7],
                        ["2014-10-01T00:00:00Z", 8],
                        ["2014-11-01T00:00:00Z", 9],
                        ["2014-12-01T00:00:00Z", 9],
                        ["2015-01-01T00:00:00Z", 12],
                        ["2015-02-01T00:00:00Z", 13],
                        ["2015-03-01T00:00:00Z", 18],
                        ["2015-04-01T00:00:00Z", 19],
                        ["2015-05-01T00:00:00Z", 19],
                        ["2015-06-01T00:00:00Z", 20],
                        ["2015-07-01T00:00:00Z", 23],
                        ["2015-08-01T00:00:00Z", 25],
                        ["2015-08-06T05:37:50.014Z", 25]
                    ]
                },
                {
                    "is_active": true,
                    "slug": "private",
                    "title": "Private",
                    "location": "/profile/plan/private/",
                    "values": [
                        ["2014-09-01T00:00:00Z", 3],
                        ["2014-10-01T00:00:00Z", 3],
                        ["2014-11-01T00:00:00Z", 3],
                        ["2014-12-01T00:00:00Z", 3],
                        ["2015-01-01T00:00:00Z", 6],
                        ["2015-02-01T00:00:00Z", 7],
                        ["2015-03-01T00:00:00Z", 10],
                        ["2015-04-01T00:00:00Z", 15],
                        ["2015-05-01T00:00:00Z", 16],
                        ["2015-06-01T00:00:00Z", 17],
                        ["2015-07-01T00:00:00Z", 17],
                        ["2015-08-01T00:00:00Z", 18],
                        ["2015-08-06T05:37:50.023Z", 18]
                    ]
                }
            ]
        }
    """

    @extend_schema(parameters=[QueryParamPeriodSerializer])
    def get(self, request, *args, **kwargs):
        return self.retrieve_metrics()


class BalancesDueAPIView(BalancesDueMixin, ListAPIView):
    """
    Lists subscribers to a provider with a balance due

    This endpoint returns a list of organizations with their respective
    total contract value, payments made, and total balance due.

    **Tags**: balance, provider, organization, subscribers

    **Examples**

    .. code-block:: http

        GET /api/metrics/cowork/balances-due HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "slug": "xia",
                    "printable_name": "Xia Lee",
                    "picture": null,
                    "type": "organization",
                    "credentials": false,
                    "created_at": "2022-08-31T19:00:00-05:00",
                    "balances": {
                        "eur": {
                            "contract_value": 1333,
                            "payments": 0,
                            "balance": 1333
                        },
                        "usd": {
                            "contract_value": 982800,
                            "cash_payments": 945000,
                            "balance": 37800
                        }
                    }
                }
            ]
        }
    """

    serializer_class = BalancesDueSerializer

    def paginate_queryset(self, queryset):
        page = super(BalancesDueAPIView, self).paginate_queryset(
            queryset)
        return self.decorate_queryset(page if page else queryset)
