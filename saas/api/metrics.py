# Copyright (c) 2014, DjaoDjin inc.
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

import datetime

from rest_framework.views import APIView
from rest_framework.response import Response

from saas.mixins import ProviderMixin
from saas.models import Transaction, Organization
from saas.utils import datetime_or_now
from saas.managers.metrics import monthly_balances
from saas.api.serializers import OrganizationSerializer


class RevenueMetricsAPIView(ProviderMixin, APIView):
    """
    Generate a table of revenue (rows) per months (columns).
    """

    def get(self, request, *args, **kwargs): #pylint: disable=unused-argument
        organization = self.get_organization()
        at_date = datetime_or_now(request.DATA.get('at', None))
        return Response([{
            'key': Transaction.INCOME,
            'values': monthly_balances(
                        organization, Transaction.INCOME, at_date)
            }])


class SubscriberPipelineAPIView(ProviderMixin, APIView):

    serializer_class = OrganizationSerializer


    def get(self, request, *args, **kwargs):
        #pylint: disable=no-member
        self.provider = self.get_organization()
        start_at = datetime_or_now(request.DATA.get('start_at', None))
        ends_at = datetime_or_now(request.DATA.get('ends_at', None))
        serializer = self.serializer_class()
        return Response({
            'start_at': start_at,
            'ends_at': ends_at,
            'churned': [serializer.to_native(organization)
                         for organization in self.churned(start_at, ends_at)],
            'ending': [serializer.to_native(organization)
                         for organization in self.ending(ends_at)],
            'registered': [serializer.to_native(organization)
                        for organization in self.registered()],
            'subscribed': [serializer.to_native(organization)
                        for organization in self.subscribed(ends_at)],
            })

    def churned(self, start_time, end_time):
        return Organization.objects.filter(
            subscription__plan__organization=self.provider,
            subscription__ends_at__gte=start_time,
            subscription__ends_at__lt=end_time)

    def ending(self, end_time):
        return Organization.objects.filter(
            subscription__plan__organization=self.provider,
            subscription__created_at__lt=end_time,
            subscription__ends_at__gte=end_time,
            subscription__ends_at__lt=end_time + datetime.timedelta(days=5))

    @staticmethod
    def registered():
        return Organization.objects.filter(subscription__isnull=True)

    def subscribed(self, end_time):
        return Organization.objects.filter(
            subscription__plan__organization=self.provider,
            subscription__created_at__lt=end_time,
            subscription__ends_at__gte=end_time + datetime.timedelta(days=5))
