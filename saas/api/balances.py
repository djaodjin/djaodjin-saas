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

from django.db.models import F, Q, Max
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.generics import (
    ListCreateAPIView, RetrieveUpdateDestroyAPIView)
from rest_framework.response import Response

from ..mixins import DateRangeMixin
from ..managers.metrics import quaterly_balances
from ..models import BalanceLine
from .serializers import BalanceLineSerializer

#pylint: disable=no-init,old-style-class

class BrokerBalancesAPIView(DateRangeMixin, APIView):
    """
    GET queries a balance sheet named ``:report`` for the broker.

    **Example request**:

    .. sourcecode:: http

        GET /api/metrics/balances/taxes/

    **Example response**:

    .. sourcecode:: http

        {
            "scale": 0.01,
            "unit": "$",
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

    def get(self, request, *args, **kwargs): #pylint: disable=unused-argument
        self.cache_fields(request)
        result = []
        report = self.kwargs.get('report')
        for line in BalanceLine.objects.filter(
                report=report).order_by('rank'):
            result += [{
                'key': line.title,
                'selector': line.selector,
                'values': quaterly_balances(
                    like_account=line.selector, until=self.ends_at)
            }]
        return Response({'title': "Balances: %s" % report,
            'unit': "$", 'scale': 0.01, 'table': result})


class BalanceLineListAPIView(ListCreateAPIView):
    """
    GET queries the list of rows reported on the balance sheet
    named ``:report`` for the broker.

    POST adds a new row on the ``:report`` balance sheet.

    **Example request**:

    .. sourcecode:: http

        GET /api/metrics/lines/taxes/

    **Example response**:

    .. sourcecode:: http

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

    **Example request**:

    .. sourcecode:: http

        POST /api/metrics/lines/taxes/

        {
          "title": "Sales",
          "selector": "Receivable",
          "rank": 1
        }

    **Example response**:

    .. sourcecode:: http

        {
          "title": "Sales",
          "selector": "Receivable",
          "rank": 1
        }
    """

    serializer_class = BalanceLineSerializer

    def get_queryset(self):
        return BalanceLine.objects.filter(
            report=self.kwargs.get('report')).order_by('rank')

    def perform_create(self, serializer):
        last_rank = self.get_queryset().aggregate(
            Max('rank')).get('rank__max', 0)
        # If the key exists and return None the default value is not applied
        last_rank = last_rank + 1 if last_rank is not None else 1
        serializer.save(report=self.kwargs.get('report'), rank=last_rank)

    def patch(self, request, *args, **kwargs):
        """
        Update the order in which lines are displayed.

        When receiving a request like [{u'newpos': 1, u'oldpos': 3}],
        it will move the line at position 3 to position 1, updating the
        rank of all lines in-between.
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

    serializer_class = BalanceLineSerializer
