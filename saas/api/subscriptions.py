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

from rest_framework import serializers
from rest_framework.generics import (get_object_or_404, ListAPIView,
    ListCreateAPIView, RetrieveUpdateDestroyAPIView, UpdateAPIView)

from ..decorators import _valid_manager
from ..filters import SortableDateRangeSearchableFilterBackend
from ..mixins import (ChurnedQuerysetMixin, PlanMixin, ProviderMixin,
    SubscriptionMixin, SubscriptionSmartListMixin, SubscribedQuerysetMixin,
    DateRangeMixin)
from .. import signals
from ..models import Subscription
from ..utils import generate_random_slug
from .roles import OptinBase
from .serializers import OrganizationSerializer, SubscriptionSerializer

#pylint: disable=no-init,old-style-class

LOGGER = logging.getLogger(__name__)


class SubscriptionCreateSerializer(serializers.ModelSerializer):

    organization = OrganizationSerializer()
    message = serializers.CharField(required=False, allow_null=True)

    class Meta:
        model = Subscription
        fields = ('organization', 'message')


class SubscriptionBaseListAPIView(SubscriptionMixin, ListCreateAPIView):

    pass


class SubscriptionListAPIView(SubscriptionSmartListMixin,
                              SubscriptionBaseListAPIView):
    """
    GET queries all ``Subscription`` of an ``Organization``. The queryset
    can be further refined to match a search filter (``q``) and sorted
    on a specific field. The returned queryset is always paginated.

    **Tags: subscriptions

    **Examples

    .. code-block:: http

        GET /api/profile/:organization/subscriptions/\
?o=created_at&ot=desc HTTP/1.1

    .. code-block:: json

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

    def post(self, request, *args, **kwargs):
        """
        Subscribes the organization to a plan.

        **Tags: subscriptions

        **Examples

        .. code-block:: http

            POST /api/profile/:organization/subscriptions/ HTTP/1.1

        .. code-block:: json

           {
               "plan": "open-space"
           }
        """
        return super(SubscriptionListAPIView, self).post(
            request, *args, **kwargs)



class SubscriptionDetailAPIView(SubscriptionMixin,
                                RetrieveUpdateDestroyAPIView):
    """
    Retrieves a ``Subscription``.

    **Tags: subscriptions

    **Examples

    .. code-block:: http

        GET /api/profile/cowork/plans/open-space/subscriptions/xia/ HTTP/1.1

    .. code-block:: json

        {
            ... XXX ...
        }
    """
    serializer_class = SubscriptionSerializer

    def delete(self, request, *args, **kwargs):
        """
        Unsubscribe an organization from a plan.

        **Tags: subscriptions

        **Examples

        .. code-block:: http

            DELETE /api/profile/cowork/plans/open-space/subscriptions/xia/\
 HTTP/1.1
        """
        return super(SubscriptionDetailAPIView, self).delete(
            request, *args, **kwargs)

    def perform_update(self, serializer):
        if not _valid_manager(
                self.request, [serializer.instance.plan.organization]):
            serializer.validated_data['created_at'] \
                = serializer.instance.created_at
            serializer.validated_data['ends_at'] = serializer.instance.ends_at
        super(SubscriptionDetailAPIView, self).perform_update(serializer)

    def perform_destroy(self, instance):
        instance.unsubscribe_now()

    def put(self, request, *args, **kwargs):
        """
        Updates an organization subscription.

        **Tags: subscriptions

        **Examples

        .. code-block:: http

            PUT /api/profile/cowork/plans/open-space/subscriptions/xia/ HTTP/1.1

        .. code-block:: json

            {
                ... XXX ...
            }

        responds

        .. code-block:: json

            {
                ... XXX ...
            }
        """
        return super(SubscriptionDetailAPIView, self).delete(
            request, *args, **kwargs)


class PlanSubscriptionsQuerysetMixin(PlanMixin):

    def get_queryset(self):
        # OK to use ``filter`` here since we want to list all subscriptions.
        return Subscription.objects.filter(
            plan__slug=self.kwargs.get(self.plan_url_kwarg),
            plan__organization=self.provider)


class PlanSubscriptionsAPIView(DateRangeMixin, SubscriptionSmartListMixin,
                             PlanSubscriptionsQuerysetMixin,
                             OptinBase, ListCreateAPIView):
    """
    A GET request will list all ``Subscription`` to
    a specified ``:plan`` provided by ``:organization``.

    **Tags: subscriptions

    **Examples

    .. code-block:: http

        GET /api/profile/:organization/plans/:plan/subscriptions/ HTTP/1.1

    .. code-block:: json

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
    """
    serializer_class = SubscriptionSerializer

    def add_relations(self, organizations, user):
        subscriptions = []
        for organization in organizations:
            # Be careful that `self.plan` must exist otherwise the API will
            # return a 404.
            if Subscription.objects.active_for(organization).filter(
                    plan=self.plan).exists():
                created = False
            else:
                created = True
                subscription = Subscription.objects.new_instance(
                    organization, plan=self.plan)
                if not self.plan.skip_optin_on_grant:
                    subscription.grant_key = generate_random_slug()
                subscription.save()
                subscriptions += [subscription]
        return subscriptions, created

    def post(self, request, *args, **kwargs):
        """
        A POST request will subscribe an organization to the ``:plan``.

        **Tags: subscriptions

        **Examples

        .. code-block:: http

            POST /api/profile/:organization/plans/:plan/subscriptions/ HTTP/1.1

        .. code-block:: json

            {
              "organization": {
                "slug": "xia"
              }
            }

        responds

        .. code-block:: json

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
        return super(PlanSubscriptionsAPIView, self).post(
            request, *args, **kwargs)

    def send_signals(self, subscriptions, user, reason=None, invite=False):
        for subscription in subscriptions:
            signals.subscription_grant_created.send(sender=__name__,
                subscription=subscription, reason=reason, invite=invite,
                request=self.request)

    def create(self, request, *args, **kwargs): #pylint:disable=unused-argument
        serializer = SubscriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_optin(serializer, request)


class PlanSubscriptionDetailAPIView(ProviderMixin, SubscriptionDetailAPIView):
    """
    Unsubscribe an organization from a plan.

    **Tags: subscriptions

    **Examples

    .. code-block:: http

        GET /api/profile/cowork/plans/open-space/subscriptions/xia/ HTTP/1.1

    .. code-block:: json

        {
            ... XXX ...
        }
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
    Lists all ``Subscription`` to a plan whose provider is
    ``{organization}`` and which are currently in progress.

    Optionnaly when an ``ends_at`` query parameter is specified,
    returns a queryset of ``Subscription`` that were active
    at ``ends_at``. When a ``start_at`` query parameter is specified,
    only considers ``Subscription`` that were created after ``start_at``.

    The queryset can be filtered for at least one field to match a search
    term (``q``).

    Query results can be ordered by natural fields (``o``) in either ascending
    or descending order (``ot``).

    **Tags: metrics

    **Examples

    .. code-block:: http

        GET /api/metrics/cowork/active?o=created_at&ot=desc HTTP/1.1

    .. code-block:: json

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
    filter_backends = (SortableDateRangeSearchableFilterBackend(
        SubscriptionSmartListMixin.sort_fields_aliases,
        SubscriptionSmartListMixin.search_fields),)


class ChurnedSubscriptionBaseAPIView(ChurnedQuerysetMixin, ListAPIView):

    pass


class ChurnedSubscriptionAPIView(SubscriptionSmartListMixin,
                                 ChurnedSubscriptionBaseAPIView):
    """
    Lists all ``Subscription`` to a plan whose provider is
    ``:organization`` which have ended already.

    The queryset can be further filtered to a range of dates between
    ``start_at`` and ``ends_at``.

    The queryset can be further filtered by passing a ``q`` parameter.
    The result queryset can be ordered.

    **Tags: metrics

    **Examples

    .. code-block:: http

        GET /api/metrics/cowork/churned?o=created_at&ot=desc HTTP/1.1

    .. code-block:: json

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
    serializer_class = SubscriptionSerializer

    def put(self, request, *args, **kwargs):
        """
        Accepts a subscription request.

        **Tags: rbac

        **Examples

        .. code-block:: http

            PUT /api/profile/xia/subscribers/accept/abcdef12 HTTP/1.1

        """
        return super(SubscriptionRequestAcceptAPIView, self).put(
            request, *args, **kwargs)

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
