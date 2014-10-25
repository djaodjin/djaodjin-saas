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

from django.db.models import Q
from django.utils.dateparse import parse_datetime
from rest_framework.views import APIView
from rest_framework.response import Response

from saas import settings
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


class OrganizationListAPIView(ProviderMixin, APIView):

    model = Organization
    serializer_class = OrganizationSerializer

    def get(self, request, *args, **kwargs):
        #pylint: disable=no-member,unused-argument
        self.provider = self.get_organization()
        start_at = request.GET.get('start_at', None)
        if start_at:
            start_at = parse_datetime(start_at)
        start_at = datetime_or_now(start_at)
        ends_at = request.GET.get('ends_at', None)
        if ends_at:
            ends_at = parse_datetime(ends_at)
        ends_at = datetime_or_now(ends_at)
        queryset = self.get_queryset(start_at, ends_at)
        serializer = self.serializer_class()
        return Response({
            'start_at': start_at,
            'ends_at': ends_at,
            'count': queryset.count(),
            self.queryset_name: [serializer.to_native(organization)
                for organization in queryset],
            })



class ChurnedAPIView(OrganizationListAPIView):

    queryset_name = 'churned'

    def get_queryset(self, start_time, end_time):
        return Organization.objects.filter(
            subscription__plan__organization=self.provider,
            subscription__ends_at__gte=start_time,
            subscription__ends_at__lt=end_time).order_by('full_name')


class RegisteredAPIView(OrganizationListAPIView):

    queryset_name = 'registered'

    def get_queryset(self, start_time, end_time):
        #pylint: disable=unused-argument
        return Organization.objects.filter(
            Q(subscription__isnull=True) |
            Q(subscription__created_at__gte=end_time), created_at__lt=end_time
            ).exclude(pk__in=[self.provider.pk, settings.PROCESSOR_ID]
            ).order_by('full_name')


class SubscribedAPIView(OrganizationListAPIView):

    queryset_name = 'subscribed'

    def get_queryset(self, start_time, end_time):
        #pylint: disable=unused-argument
        return Organization.objects.filter(
            subscription__plan__organization=self.provider,
            subscription__created_at__lt=end_time,
            subscription__ends_at__gte=end_time).order_by(
            'subscription__ends_at', 'full_name')
