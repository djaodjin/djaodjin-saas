# Copyright (c) 2017, DjaoDjin inc.
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

from rest_framework import serializers
from rest_framework.generics import (get_object_or_404, ListAPIView,
    ListCreateAPIView, RetrieveUpdateDestroyAPIView, UpdateAPIView)

from ..decorators import _valid_manager
from ..mixins import (ChurnedQuerysetMixin, PlanMixin, ProviderMixin,
    SubscriptionMixin, SubscriptionSmartListMixin, SubscribedQuerysetMixin)
from ..models import Subscription
from .. import signals
from .roles import OptinBase
from .serializers import OrganizationSerializer, SubscriptionSerializer

#pylint: disable=no-init,old-style-class

LOGGER = logging.getLogger(__name__)


class SubscriptionCreateSerializer(serializers.ModelSerializer):

    organization = OrganizationSerializer()

    class Meta:
        model = Subscription
        fields = ('organization',)


class SubscriptionBaseListAPIView(SubscriptionMixin, ListCreateAPIView):

    pass


class SubscriptionListAPIView(SubscriptionSmartListMixin,
                              SubscriptionBaseListAPIView):
    """
    GET queries all ``Subscription`` of an ``Organization``. The queryset
    can be further refined to match a search filter (``q``) and sorted
    on a specific field. The returned queryset is always paginated.

    The value passed in the ``q`` parameter will be matched against:

      - Subscription.organization.slug
      - Subscription.organization.full_name
      - Subscription.organization.email
      - Subscription.organization.phone
      - Subscription.organization.street_address
      - Subscription.organization.locality
      - Subscription.organization.region
      - Subscription.organization.postal_code
      - Subscription.organization.country
      - Subscription.plan.title

    The result queryset can be ordered by:

      - Subscription.created_at
      - Subscription.ends_at
      - Subscription.organization.full_name
      - Subscription.plan.title

    **Example request**:

    .. sourcecode:: http

        GET /api/profile/:organization/subscriptions/?o=created_at&ot=desc

    **Example response**:

    .. sourcecode:: http

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2016-01-14T23:16:55Z",
                    "ends_at": "2017-01-14T23:16:55Z",
                    "description": null,
                    "organization": {
                        "slug": "xia",
                        "printable_name": "Xia Lee"
                    },
                    "plan": {
                        "slug": "open-space",
                        "title": "Open Space",
                        "description": "open space desk, High speed internet
                                      - Ethernet or WiFi, Unlimited printing,
                                      Unlimited scanning, Unlimited fax service
                                      (send and receive)",
                        "is_active": true,
                        "setup_amount": 0,
                        "period_amount": 17999,
                        "interval": 4,
                        "app_url": "http://localhost:8020/app"
                    },
                    "auto_renew": true
                }
            ]
        }

    POST subscribes the organization to a plan.
    """

    serializer_class = SubscriptionSerializer


class SubscriptionDetailAPIView(SubscriptionMixin,
                                RetrieveUpdateDestroyAPIView):
    """
    Unsubscribe an organization from a plan.
    """

    serializer_class = SubscriptionSerializer

    def perform_update(self, serializer):
        if not _valid_manager(
                self.request.user, [serializer.instance.plan.organization]):
            serializer.validated_data['created_at'] \
                = serializer.instance.created_at
            serializer.validated_data['ends_at'] = serializer.instance.ends_at
        super(SubscriptionDetailAPIView, self).perform_update(serializer)

    def perform_destroy(self, instance):
        instance.unsubscribe_now()


class PlanSubscriptionsQuerysetMixin(PlanMixin):

    def get_queryset(self):
        # OK to use ``filter`` here since we want to list all subscriptions.
        return Subscription.objects.filter(
            plan__slug=self.kwargs.get(self.plan_url_kwarg),
            plan__organization=self.provider)


class PlanSubscriptionsAPIView(SubscriptionSmartListMixin,
                             PlanSubscriptionsQuerysetMixin,
                             OptinBase, ListCreateAPIView):
    """
    A GET request will list all ``Subscription`` to
    a specified ``:plan`` provided by ``:organization``.

    A POST request will subscribe an organization to the ``:plan``.

    The value passed in the ``q`` parameter will be matched against:

      - Organization.slug
      - Organization.full_name
      - Organization.email
      - Organization.phone
      - Organization.street_address
      - Organization.locality
      - Organization.region
      - Organization.postal_code
      - Organization.country

    The result queryset can be ordered by:

      - Organization.created_at
      - Organization.full_name

    **Example request**:

    .. sourcecode:: http

        GET /api/profile/:organization/plans/:plan/subscriptions/

    **Example response**:

    .. sourcecode:: http

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                "slug": "xia",
                "full_name": "Xia Lee",
                "created_at": "2016-01-14T23:16:55Z"
                }
            ]
        }

    **Example request**:

    .. sourcecode:: http

        POST /api/profile/:organization/plans/:plan/subscriptions/

        {
          "organizatoin": {
            "slug": "xia"
          }
        }

    **Example response**:

    .. sourcecode:: http

        201 CREATED
        {
          "created_at": "2016-01-14T23:16:55Z",
          "ends_at": "2017-01-14T23:16:55Z",
          "description": null,
          "organization": {
            "slug": "xia",
            "printable_name": "Xia Lee"
          },
          "plan": {
            "slug": "open-space",
            "title": "Open Space",
            "description": "open space desk, High speed internet
                              - Ethernet or WiFi, Unlimited printing,
                                Unlimited scanning, Unlimited fax service
                                (send and receive)",
            "is_active": true,
            "setup_amount": 0,
            "period_amount": 17999,
            "interval": 4,
            "app_url": "http://localhost:8020/app"
          },
          "auto_renew": true
        }
    """
    serializer_class = SubscriptionSerializer

    def add_relations(self, organizations, user, reason=None):
        subscriptions = []
        for organization in organizations:
            if Subscription.objects.active_for(organization).filter(
                    plan=self.plan).exists():
                created = False
            else:
                created = True
                subscription = Subscription.objects.new_instance(
                    organization, plan=self.plan)
                if not self.plan.skip_optin_on_grant:
                    subscription.grant_key = \
                        self.plan.organization.generate_role_key(user)
                subscription.save()
                subscriptions += [subscription]
        for subscription in subscriptions:
            signals.subscription_grant_created.send(sender=__name__,
                subscription=subscription, reason=reason, request=self.request)
        return created

    def create(self, request, *args, **kwargs): #pylint:disable=unused-argument
        serializer = SubscriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_optin(serializer, request)


class PlanSubscriptionDetailAPIView(ProviderMixin, SubscriptionDetailAPIView):
    """
    Unsubscribe an organization from a plan.
    """
    subscriber_url_kwarg = 'subscriber'

    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        return super(PlanSubscriptionDetailAPIView, self).get_queryset().filter(
            plan__organization=self.provider)


class ActiveSubscriptionBaseAPIView(SubscribedQuerysetMixin, ListAPIView):

    pass


class ActiveSubscriptionAPIView(SubscriptionSmartListMixin,
                                ActiveSubscriptionBaseAPIView):
    """
    GET queries all ``Subscription`` to a plan whose provider is
    ``:organization`` which are currently in progress.

    The queryset can be further filtered to a range of dates between
    ``start_at`` and ``ends_at``.

    The queryset can be further filtered by passing a ``q`` parameter.
    The value in ``q`` will be matched against:

      - Subscription.organization.slug
      - Subscription.organization.full_name
      - Subscription.organization.email
      - Subscription.organization.phone
      - Subscription.organization.street_address
      - Subscription.organization.locality
      - Subscription.organization.region
      - Subscription.organization.postal_code
      - Subscription.organization.country
      - Subscription.plan.title

    The result queryset can be ordered by:

      - Subscription.created_at
      - Subscription.ends_at
      - Subscription.organization.full_name
      - Subscription.plan.title

    **Example request**:

    .. sourcecode:: http

        GET /api/metrics/cowork/active?o=created_at&ot=desc

    **Example response**:

    .. sourcecode:: http

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2016-01-14T23:16:55Z",
                    "ends_at": "2017-01-14T23:16:55Z",
                    "description": null,
                    "organization": {
                        "slug": "xia",
                        "printable_name": "Xia Lee"
                    },
                    "plan": {
                        "slug": "open-space",
                        "title": "Open Space",
                        "description": "open space desk, High speed internet
                                    - Ethernet or WiFi, Unlimited printing,
                                    Unlimited scanning, Unlimited fax service
                                    (send and receive)",
                        "is_active": true,
                        "setup_amount": 0,
                        "period_amount": 17999,
                        "interval": 4,
                        "app_url": "http://localhost:8020/app"
                    },
                    "auto_renew": true
                }
            ]
        }
    """
    serializer_class = SubscriptionSerializer


class ChurnedSubscriptionBaseAPIView(ChurnedQuerysetMixin, ListAPIView):

    pass


class ChurnedSubscriptionAPIView(SubscriptionSmartListMixin,
                                 ChurnedSubscriptionBaseAPIView):
    """
    GET queries all ``Subscription`` to a plan whose provider is
    ``:organization`` which have ended already.

    The queryset can be further filtered to a range of dates between
    ``start_at`` and ``ends_at``.

    The queryset can be further filtered by passing a ``q`` parameter.
    The value in ``q`` will be matched against:

      - Subscription.organization.slug
      - Subscription.organization.full_name
      - Subscription.organization.email
      - Subscription.organization.phone
      - Subscription.organization.street_address
      - Subscription.organization.locality
      - Subscription.organization.region
      - Subscription.organization.postal_code
      - Subscription.organization.country
      - Subscription.plan.title

    The result queryset can be ordered by:

      - Subscription.created_at
      - Subscription.ends_at
      - Subscription.organization.full_name
      - Subscription.plan.title

    **Example request**:

    .. sourcecode:: http

        GET /api/metrics/cowork/churned?o=created_at&ot=desc

    **Example response**:

    .. sourcecode:: http

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2016-01-14T23:16:55Z",
                    "ends_at": "2017-01-14T23:16:55Z",
                    "description": null,
                    "organization": {
                        "slug": "xia",
                        "printable_name": "Xia Lee"
                    },
                    "plan": {
                        "slug": "open-space",
                        "title": "Open Space",
                        "description": "open space desk, High speed internet
                                    - Ethernet or WiFi, Unlimited printing,
                                    Unlimited scanning, Unlimited fax service
                                    (send and receive)",
                        "is_active": true,
                        "setup_amount": 0,
                        "period_amount": 17999,
                        "interval": 4,
                        "app_url": "http://localhost:8020/app"
                    },
                    "auto_renew": true
                }
            ]
        }
    """
    serializer_class = SubscriptionSerializer


class SubscriptionRequestAcceptAPIView(UpdateAPIView):

    provider_url_kwarg = 'organization'
    serializer_class = serializers.Serializer

    def get_queryset(self):
        return Subscription.objects.active_with(
            self.kwargs.get(self.provider_url_kwarg))

    @property
    def subscription(self):
        if not hasattr(self, '_subscription'):
            self._subscription = get_object_or_404(self.get_queryset(),
                request_key=self.kwargs.get('request_key'))
        return self._subscription

    def get_object(self):
        return self.subscription

    def perform_update(self, serializer):
        request_key = serializer.instance.request_key
        serializer.instance.request_key = None
        serializer.instance.save()
        LOGGER.info(
            "%s accepted subscription of %s to plan %s (request_key=%s)",
            self.request.user, serializer.instance.organization,
            serializer.instance.plan, request_key, extra={
                'request': self.request, 'event': 'accept',
                'user': str(self.request.user),
                'organization': str(serializer.instance.organization),
                'plan': str(serializer.instance.plan),
                'ends_at': str(serializer.instance.ends_at),
                'request_key': request_key})
        signals.subscription_request_accepted.send(sender=__name__,
            subscription=serializer.instance,
            request_key=request_key, request=self.request)
