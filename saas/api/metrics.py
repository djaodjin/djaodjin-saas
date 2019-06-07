# Copyright (c) 2019, DjaoDjin inc.
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

from django.utils.translation import ugettext_lazy as _
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response

from ..compat import reverse
from ..filters import DateRangeFilter
from .. import settings
from ..mixins import (CartItemSmartListMixin, CouponMixin,
    ProviderMixin, DateRangeContextMixin)
from ..models import CartItem, Plan, Transaction
from ..utils import convert_dates_to_utc
from .serializers import CartItemSerializer
from ..managers.metrics import (abs_monthly_balances, active_subscribers,
    aggregate_transactions_by_period, month_periods, churn_subscribers,
    aggregate_transactions_change_by_period, get_different_units)
from .serializers import MetricsSerializer

LOGGER = logging.getLogger(__name__)


class BalancesAPIView(DateRangeContextMixin, ProviderMixin,
                      GenericAPIView):
    """
    Generate a table of revenue (rows) per months (columns).

    **Tags: metrics

    **Examples

    .. code-block:: http

        GET /api/metrics/cowork/balances HTTP/1.1

    .. code-block:: json

        {
            "title": "Balances",
            "scale": 0.01,
            "unit": "usd",
            "table": [
                {
                    "key": "Income",
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
                    ],
                },
                {
                    "key": "Backlog",
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
                    ],
                },
                {
                    "key": "Receivable",
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
                    ],
                }
            ]
        }
    """
    serializer_class = MetricsSerializer
    filter_backends = (DateRangeFilter,)

    def get(self, request, *args, **kwargs): #pylint: disable=unused-argument
        result = []
        unit = settings.DEFAULT_UNIT
        for key in [Transaction.INCOME, Transaction.BACKLOG,
                    Transaction.RECEIVABLE]:
            values, _unit = abs_monthly_balances(
                organization=self.provider, account=key,
                until=self.ends_at, tz=self.timezone)

            if _unit:
                unit = _unit

            result += [{
                'key': key,
                'values': values
            }]
        return Response({'title': "Balances",
            'unit': unit, 'scale': 0.01, 'table': result})


class RevenueMetricAPIView(DateRangeContextMixin, ProviderMixin,
                           GenericAPIView):
    """
    Produces sales, payments and refunds over a period of time.

    **Tags: metrics

    **Examples

    .. code-block:: http

        GET /api/metrics/cowork/funds/ HTTP/1.1

    .. code-block:: json

        {
            "title": "Amount",
            "scale": 0.01,
            "unit": "usd",
            "table": [
                {
                    "key": "Total Sales",
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
                    "key": "New Sales",
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
                    "key": "Churned Sales",
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
                    "key": "Payments",
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
                    "key": "Refunds",
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
            ],
        }
    """
    serializer_class = MetricsSerializer
    filter_backends = (DateRangeFilter,)

    def get(self, request, *args, **kwargs):
        #pylint:disable=unused-argument
        dates = convert_dates_to_utc(
            month_periods(12, self.ends_at, tz=self.timezone))

        unit = settings.DEFAULT_UNIT

        account_table, _, _, table_unit = \
            aggregate_transactions_change_by_period(self.provider,
                Transaction.RECEIVABLE, account_title='Sales',
                orig='orig', dest='dest',
                date_periods=dates)

        _, payment_amounts, payments_unit = aggregate_transactions_by_period(
            self.provider, Transaction.RECEIVABLE,
            orig='dest', dest='dest',
            orig_account=Transaction.BACKLOG,
            orig_organization=self.provider,
            date_periods=dates)

        _, refund_amounts, refund_unit = aggregate_transactions_by_period(
            self.provider, Transaction.REFUND,
            orig='dest', dest='dest',
            date_periods=dates)

        units = get_different_units(table_unit, payments_unit, refund_unit)

        if len(units) > 1:
            LOGGER.error("different units: %s", units)

        if units:
            unit = units[0]

        account_table += [
            {"key": "Payments", "values": payment_amounts},
            {"key": "Refunds", "values": refund_amounts}]

        return Response(
            {"title": "Amount",
            "unit": unit, "scale": 0.01, "table": account_table})


class CouponUsesQuerysetMixin(object):

    def get_queryset(self):
        return CartItem.objects.filter(coupon=self.coupon, recorded=True)


class CouponUsesAPIView(CartItemSmartListMixin, CouponUsesQuerysetMixin,
                        CouponMixin, ListAPIView):
    """
    Queries a page (``PAGE_SIZE`` records) of ``Coupon`` usage.

    The queryset can be filtered to a range of dates
    ([``start_at``, ``ends_at``]) and for at least one field to match a search
    term (``q``).

    The result queryset can be ordered by passing an ``o`` (field name)
    and ``ot`` (asc or desc) parameter.

    **Tags: metrics

    **Examples

    .. code-block:: http

        GET /api/metrics/cowork/coupons/DIS100/ HTTP/1.1

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "user": {
                        "slug": "xia",
                        "email": "xia@localhost.localdomain",
                        "full_name": "Xia Doe",
                        "created_at": "2012-09-14T23:16:55Z"
                    },
                    "plan": "basic",
                    "created_at": "2014-01-01T09:00:00Z"
                }
            ]
        }
    """
    forced_date_range = False
    serializer_class = CartItemSerializer


class CustomerMetricAPIView(DateRangeContextMixin, ProviderMixin,
                            GenericAPIView):
    """
    Produce revenue stats

    **Tags: metrics

    **Examples

    .. code-block:: http

        GET /api/metrics/cowork/customers HTTP/1.1

    .. code-block:: json

        {
            "title": "Customers"
            "table": [
                {
                    "key": "Total # of Customers",
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
                    "key": "# of new Customers"
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
                    "key": "# of churned Customers"
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
                    "key": "Net New Customers",
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
            ],
            "extra": [
                {
                    "key": "% Customer Churn",
                    "values": [
                        ["2014-10-01T00:00:00Z", 0],
                        ["2014-11-01T00:00:00Z", 0.0],
                        ["2014-12-01T00:00:00Z", 0.0],
                        ["2015-01-01T00:00:00Z", 0.0],
                        ["2015-02-01T00:00:00Z", 0.0],
                        ["2015-03-01T00:00:00Z", 0.0],
                        ["2015-04-01T00:00:00Z", 0.0],
                        ["2015-05-01T00:00:00Z", 0.0],
                        ["2015-06-01T00:00:00Z", 0.0],
                        ["2015-07-01T00:00:00Z", 0.0],
                        ["2015-08-01T00:00:00Z", 2.08],
                        ["2015-08-06T05:20:24.537Z", 111.11]
                    ]
                }
            ]
        }
    """
    serializer_class = MetricsSerializer
    filter_backends = (DateRangeFilter,)

    def get(self, request, *args, **kwargs):
        #pylint:disable=unused-argument
        account_title = 'Payments'
        account = Transaction.RECEIVABLE
        # We use ``Transaction.RECEIVABLE`` which technically counts the number
        # or orders, not the number of payments.

        dates = convert_dates_to_utc(
            month_periods(12, self.ends_at, tz=self.timezone))
        _, customer_table, customer_extra, _ = \
            aggregate_transactions_change_by_period(self.provider, account,
                account_title=account_title,
                date_periods=dates)

        return Response(
            {"title": "Customers",
                "table": customer_table, "extra": customer_extra})


class PlanMetricAPIView(DateRangeContextMixin, ProviderMixin, GenericAPIView):
    """
    Produce plan stats

    **Tags: metrics

    **Examples

    .. code-block:: http

        GET /api/metrics/cowork/plans HTTP/1.1

    .. code-block:: json

        {
            "title": "Active Subscribers",
            "table": [
                {
                    "is_active": true,
                    "key": "open-space",
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
                    "key": "open-plus",
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
                    "key": "private",
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
            ],
            "extra": [
                {
                    "key": "churn",
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
                        ["2015-08-01T00:00:00Z", 1],
                        ["2015-08-06T05:37:50.031Z", 1]
                    ]
                }
            ]
        }
    """
    serializer_class = MetricsSerializer
    filter_backends = (DateRangeFilter,)

    def get(self, request, *args, **kwargs):
        #pylint:disable=unused-argument
        table = []
        for plan in Plan.objects.filter(
                organization=self.provider).order_by('title'):
            values = active_subscribers(
                plan, from_date=self.ends_at, tz=self.timezone)
            table.append({
                "key": plan.slug,
                "title": plan.title,
                "values": values,
                "location": reverse(
                    'saas_plan_edit', args=(self.provider, plan)),
                "is_active": plan.is_active})
        extra = [{"key": "churn",
            "values": churn_subscribers(
                from_date=self.ends_at, tz=self.timezone)}]

        return Response(
            {"title": _("Active subscribers"),
                "table": table, "extra": extra})
