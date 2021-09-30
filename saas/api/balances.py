# Copyright (c) 2021, DjaoDjin inc.
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

#pylint:disable=useless-super-delegation

from django.db import transaction
from django.db.models import F, Q, Max
from rest_framework.generics import (get_object_or_404,
    GenericAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView)
from rest_framework.response import Response

from .. import settings
from ..docs import swagger_auto_schema, OpenAPIResponse
from ..metrics.base import abs_monthly_balances, monthly_balances
from ..models import BalanceLine
from ..filters import DateRangeFilter
from ..mixins import DateRangeContextMixin
from .serializers import (BalanceLineSerializer, MetricsSerializer,
    UpdateRankSerializer)

#pylint: disable=no-init

class BrokerBalancesAPIView(DateRangeContextMixin, GenericAPIView):
    """
    Retrieves a balance sheet

    Queries a balance sheet named ``{report}`` for the broker.

    To add lines in the report see `/api/metrics/balances/{report}/lines/`.

    **Tags**: metrics, broker, transactionmodel

    **Examples**

    .. code-block:: http

        GET /api/metrics/balances/taxes/ HTTP/1.1

    responds

    .. code-block:: json

        {
            "scale": 0.01,
            "unit": "usd",
            "title": "Balances: taxes",
            "table": [
                {
                    "key": "Sales",
                    "selector": "Receivable",
                    "values": [
                        ["2015-05-01T00:00:00Z", 0],
                        ["2015-08-01T00:00:00Z", 0],
                        ["2015-11-01T00:00:00Z", 0],
                        ["2016-02-01T00:00:00Z", 0],
                        ["2016-05-01T00:00:00Z", 0],
                        ["2016-05-16T21:08:15.637Z", 0]
                    ]
                }
            ]
        }
    """
    serializer_class = MetricsSerializer
    filter_backends = (DateRangeFilter,)

    def get(self, request, *args, **kwargs): #pylint: disable=unused-argument
        result = []
        report = self.kwargs.get('report')
        unit = settings.DEFAULT_UNIT
        for line in BalanceLine.objects.filter(report=report).order_by('rank'):
            if line.is_positive:
                balances_func = abs_monthly_balances
            else:
                balances_func = monthly_balances
            values, _unit = balances_func(
                like_account=line.selector, until=self.ends_at)
            if _unit:
                unit = _unit

            result += [{
                'key': line.title,
                'selector': line.selector,
                'values': values
            }]
        return Response({'title': "Balances: %s" % report,
            'unit': unit, 'scale': 0.01, 'table': result})


class BalanceLineListAPIView(ListCreateAPIView):
    """
    Retrieves row headers for a balance sheet

    Queries the list of rows reported on a balance sheet named `{report}`.

    **Tags**: metrics, broker, transactionmodel

    **Examples**

    .. code-block:: http

        GET  /api/metrics/balances/taxes/lines/ HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "title": "Sales",
                    "selector": "Receivable",
                    "rank": 1
                }
            ]
        }
    """
    serializer_class = BalanceLineSerializer
    queryset = BalanceLine.objects.all()

    def get_serializer_class(self):
        if self.request.method.lower() in ('patch',):
            return UpdateRankSerializer
        return super(BalanceLineListAPIView, self).get_serializer_class()

    def get_queryset(self):
        return self.queryset.filter(
            report=self.kwargs.get('report')).order_by('rank')

    def perform_create(self, serializer):
        last_rank = self.get_queryset().aggregate(
            Max('rank')).get('rank__max', 0)
        # If the key exists and return None the default value is not applied
        last_rank = last_rank + 1 if last_rank is not None else 1
        serializer.save(report=self.kwargs.get('report'), rank=last_rank)

    def post(self, request, *args, **kwargs):
        """
        Creates a row in a balance sheet

        Adds a new row on the ``{report}`` balance sheet.

        **Tags**: metrics, broker, transactionmodel

        **Examples**

        .. code-block:: http

            POST /api/metrics/balances/taxes/lines/ HTTP/1.1

        .. code-block:: json

            {
              "title": "Sales",
              "selector": "Receivable",
              "rank": 1
            }

        responds

        .. code-block:: json

            {
              "title": "Sales",
              "selector": "Receivable",
              "rank": 1
            }
        """
        return super(BalanceLineListAPIView, self).post(
            request, *args, **kwargs)

    @swagger_auto_schema(responses={
        200: OpenAPIResponse("success", BalanceLineSerializer(many=True))})
    def patch(self, request, *args, **kwargs):
        """
        Updates the order in which lines are displayed

        When receiving a request like [{"newpos": 1, "oldpos": 3}],
        it will move the line at position 3 to position 1, updating the
        rank of all lines in-between.

        **Tags**: metrics, broker, transactionmodel

        **Examples**

        .. code-block:: http

            PATCH /api/metrics/balances/taxes/lines/ HTTP/1.1

        .. code-block:: json

            [{
              "newpos": 1,
              "oldpos": 3
            }]

        responds

        .. code-block:: json

            {
                "count": 1,
                "next": null,
                "previous": null,
                "results": [
                    {
                        "title": "Sales",
                        "selector": "Receivable",
                        "rank": 1
                    }
                ]
            }
        """
        with transaction.atomic():
            for move in request.data:
                oldpos = move['oldpos']
                newpos = move['newpos']
                queryset = self.get_queryset()
                updated = queryset.get(rank=oldpos)
                if newpos < oldpos:
                    queryset.filter(Q(rank__gte=newpos)
                                    & Q(rank__lt=oldpos)).update(
                        rank=F('rank') + 1, moved=True)
                else:
                    queryset.filter(Q(rank__lte=newpos)
                                    & Q(rank__gt=oldpos)).update(
                        rank=F('rank') - 1, moved=True)
                updated.rank = newpos
                updated.moved = True
                updated.save(update_fields=['rank', 'moved'])
                queryset.filter(moved=True).update(moved=False)
        return self.get(request, *args, **kwargs)


class BalanceLineDetailAPIView(RetrieveUpdateDestroyAPIView):
    """
    Retrieves a row in a balance sheet

    Describes a row reported on a balance sheet named `{report}`.

    **Tags**: metrics, broker, transactionmodel

    **Examples**

    .. code-block:: http

        GET  /api/metrics/balances/taxes/lines/1/ HTTP/1.1

    responds

    .. code-block:: json

        {
            "title": "Sales",
            "selector": "Receivable",
            "rank": 1
        }
    """
    serializer_class = BalanceLineSerializer
    queryset = BalanceLine.objects.all()

    def get_queryset(self):
        return self.queryset.filter(report=self.kwargs.get('report'))

    def put(self, request, *args, **kwargs):
        """
        Updates a row in a balance sheet

        Updates a row reported on a balance sheet named `{report}`.

        **Tags**: metrics, broker, transactionmodel

        **Examples**

        .. code-block:: http

            PUT /api/metrics/balances/taxes/lines/1/ HTTP/1.1

        .. code-block:: json

            {
              "title": "Sales",
              "selector": "Receivable",
              "rank": 1
            }

        responds

        .. code-block:: json

            {
              "title": "Sales",
              "selector": "Receivable",
              "rank": 1
            }
        """
        return super(BalanceLineDetailAPIView, self).put(
            request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        """
        Deletes a row in a balance sheet

        Deletes a row reported on a balance sheet named `{report}`.

        **Tags**: metrics, broker, transactionmodel

        **Examples**

        .. code-block:: http

            DELETE /api/metrics/balances/taxes/lines/1/ HTTP/1.1
        """
        return super(BalanceLineDetailAPIView, self).delete(
            request, *args, **kwargs)

    def get_object(self):
        return get_object_or_404(self.get_queryset(),
            rank=self.kwargs.get('rank'))
