# Copyright (c) 2022, DjaoDjin inc.
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

from collections import OrderedDict

from dateutil.relativedelta import relativedelta
from django.db.models import Count, Max, Min, Q
from rest_framework import generics
from rest_framework.response import Response as HttpResponse

from .serializers import MetricsSerializer
from ..compat import six
from ..models import Plan
from ..mixins import DateRangeContextMixin, ProviderMixin
from ..utils import datetime_or_now, get_organization_model


class FederatedMetricsMixin(DateRangeContextMixin, ProviderMixin):

    scale = 1
    unit = 'profiles'

    def get_members(self, ends_at=None):
        return get_organization_model().objects.filter(
            subscription__plan__organzation=self.provider,
            subscription__ends_at__gte=datetime_or_now(ends_at))


class FederatedSubscribersAPIView(FederatedMetricsMixin,
                                  generics.RetrieveAPIView):
    """
    Retrieves churned vs. new subscribers for a federation

    Returns the number of churned vs. new subscribers per plans for a period
    for all members of a federation of provider.

    **Tags**: metrics, provider

    **Examples**

    .. code-block:: http

        GET /api/metrics/cowork/federated/ HTTP/1.1

    responds

    .. code-block:: json

        {
          "title": "Invited",
          "scale": 1,
          "unit": "profiles",
          "table": [{
            "key":"removed profiles",
            "values":[
              ["Energy utility",0]
            ]
          }, {
            "key":"invited profiles",
            "values":[
              ["Energy utility",0]
            ]
          }, {
            "key":"newly invited profiles",
            "values":[
              ["Energy utility",0]
            ]
          }]
        }
    """
    title = 'invited profiles'
    serializer_class = MetricsSerializer

    def get(self, request, *args, **kwargs):
        #pylint:disable=too-many-locals
        self._start_time()
        period_end = datetime_or_now(self.ends_at)
        period_begin = datetime_or_now(self.start_at)
        period_start = period_end - relativedelta(years=1)

        members = self.get_members(ends_at=period_end)

        subscribed_to_members = Plan.objects.filter(
            organization__in=members).values_list('pk', flat=True)

        by_plans = OrderedDict({})
        for member in members.order_by(
                'full_name').values_list('full_name', flat=True):
            by_plans.update({member: [0, 0, 0]})

        plan_key = 'organization__full_name'
        # churned before the reporting period, i.e. subscription ends before
        # *period_begin*.
        churned_by_plans = Plan.objects.filter(
          pk__in=subscribed_to_members,
          subscription__ends_at__lt=period_begin).annotate(
          nb_subscribers=Count('subscription__organization_id')).values(
              plan_key, 'nb_subscribers')

        # active subscription in the reporting period.
        active_by_plans = Plan.objects.filter(
            pk__in=subscribed_to_members,
            subscription__created_at__lt=period_end,
            subscription__ends_at__gte=period_end).annotate(
           nb_subscribers=Count('subscription__organization_id')).values(
              plan_key, 'nb_subscribers')

        # newly active subscription that was created in the reporting period,
        # ie. [period_start, period_end[.
        newly_active_by_plans = Plan.objects.filter(
            pk__in=subscribed_to_members,
            subscription__created_at__gte=period_start,
            subscription__created_at__lt=period_end,
            subscription__ends_at__gte=period_end).annotate(
            nb_subscribers=Count(
                'subscription__organization_id')).values(
                plan_key, 'nb_subscribers')

        for row in churned_by_plans:
            member = row[plan_key]
            nb_subscribers = - row['nb_subscribers']
            by_plans[member][0] = nb_subscribers

        for row in newly_active_by_plans:
            member = row[plan_key]
            nb_subscribers = row['nb_subscribers']
            by_plans[member][2] = nb_subscribers

        for row in active_by_plans:
            member = row[plan_key]
            nb_subscribers = (row['nb_subscribers'] - by_plans[member][2])
            by_plans[member][1] = nb_subscribers

        by_subscribers = get_organization_model().objects.filter(
            Q(subscription__plan__organization=self.provider) |
            Q(subscription__plan__in=subscribed_to_members)).annotate(
                starts_at=Min('subscriptions__created_at'),
                ends_at=Max('subscriptions__ends_at'))

        removed_total = by_subscribers.filter(
            ends_at__lt=period_begin)

        invited_total = by_subscribers.filter(
            starts_at__lt=period_end,
            ends_at__gte=period_end)
        newly_invited_total = by_subscribers.filter(
            starts_at__gte=period_start,
            starts_at__lt=period_end,
            ends_at__gte=period_end)
        newly_invited_total_count = newly_invited_total.count()

        by_plans.update({
            self.provider.full_name: [
                - removed_total.count(),
                invited_total.count() - newly_invited_total_count,
                newly_invited_total_count
            ]
        })

        churned_by_plans_data = [[member, counts[0]]
            for member, counts in six.iteritems(by_plans)]
        prev_active_by_plans_data = [[member, counts[1]]
            for member, counts in six.iteritems(by_plans)]
        newly_active_by_plans_data = [[member, counts[2]]
            for member, counts in six.iteritems(by_plans)]

        resp = {
            "title": self.title,
            'scale': self.scale,
            'unit': self.unit,
            'table': [
                {
                    "key": "churned",
                    "values": churned_by_plans_data
                },
                {
                    "key": "previously subscribed",
                    "values": prev_active_by_plans_data
                },
                {
                    "key": "newly subscribed",
                    "values": newly_active_by_plans_data
                }
            ]
        }
        return HttpResponse(resp)


class SharedProfilesAPIView(FederatedMetricsMixin,
                            generics.RetrieveAPIView):
    """
    Retrieves shared profiles within a federation

    Returns the number of shared profiles

    **Tags**: metrics, provider

    **Examples**

    .. code-block:: http

        GET /api/metrics/cowork/federated/shared/ HTTP/1.1

    responds

    .. code-block:: json

        {
          "title": "Invited",
          "scale": 1,
          "unit": "profiles",
          "table": [{
            "key": "removed profiles",
            "values": [
              ["Energy utility",0]
            ]
          }, {
            "key": "invited profiles",
            "values": [
              ["Energy utility",0]
            ]
          }, {
            "key": "newly invited profiles",
            "values": [
              ["Energy utility",0]
            ]
          }]
        }
    """
    title = 'shared profiles'
    serializer_class = MetricsSerializer

    def get(self, request, *args, **kwargs):
        period_end = datetime_or_now(self.ends_at)

        members = self.get_members(ends_at=period_end)

        by_subscribers = get_organization_model().objects.filter(
            subscriptions__ends_at__gt=period_end,
            subscription__plan__organization=members).annotate(
                nb_subscriptions=Count('subscriptions__plan'))

# XXX maybe use this in loop below instead?
#        reporting_entities = by_subscribers.filter(
#                    nb_subscriptions__gt=1).order_by('nb_subscriptions')

        # XXX couldn't figure out how to do this with the Django ORM.
        by_profiles = OrderedDict({})
        for row in by_subscribers.order_by(
                'nb_subscriptions').values_list('id', 'nb_subscriptions'):
            # for reference:
            #   profile_id = row[0]
            nb_subscriptions = row[1]
            by_profiles.update({
                nb_subscriptions: by_profiles.get(nb_subscriptions, 0) + 1
            })

        by_profiles = [[key, val] for key, val in six.iteritems(by_profiles)]

        resp = {
            "title": self.title,
            'scale': self.scale,
            'unit': self.unit,
            'table': [
                {
                    "key": "shared",
                    "values": by_profiles
                }
            ]
        }
        return HttpResponse(resp)
