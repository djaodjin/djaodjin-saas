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

#pylint:disable=useless-super-delegation

import logging

from rest_framework.generics import (get_object_or_404, CreateAPIView,
    ListAPIView, ListCreateAPIView, RetrieveAPIView)
from rest_framework.mixins import DestroyModelMixin, UpdateModelMixin

from ..decorators import _valid_manager
from ..docs import swagger_auto_schema
from ..filters import DateRangeFilter
from ..mixins import (ChurnedQuerysetMixin, PlanSubscribersQuerysetMixin,
    ProviderMixin, SubscriptionMixin, SubscriptionSmartListMixin,
    SubscribedQuerysetMixin)
from .. import signals
from ..models import Subscription
from ..utils import generate_random_slug, datetime_or_now
from .roles import OptinBase
from .serializers import (ForceSerializer, SubscriptionSerializer,
    SubscriptionCreateSerializer)

#pylint: disable=no-init,old-style-class

LOGGER = logging.getLogger(__name__)


class SubscriptionBaseListAPIView(SubscriptionMixin, ListCreateAPIView):

    pass


class SubscriptionListCreateAPIView(SubscriptionSmartListMixin,
                                    SubscriptionBaseListAPIView):
    """
    Lists subscriptions

    Returns a PAGE_SIZE list of subscriptions past and present for
    subscriber {organization}.

    The queryset can be further refined to match a search filter (``q``)
    and sorted on specific fields (``o``).

    **Tags: subscriptions

    **Examples

    .. code-block:: http

        GET /api/profile/cowork/subscriptions/?o=created_at&ot=desc HTTP/1.1

    responds

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
        Subscribes to a plan

        Subscribes {organization} to a plan specified in the request body.

        **Tags: subscriptions

        **Examples

        .. code-block:: http

            POST /api/profile/xia/subscriptions/ HTTP/1.1

        .. code-block:: json

           {
               "plan": "open-space"
           }

        responds

        .. code-block:: json

             {
               "created_at": "2019-01-01T00:00:00Z",
               "ends_at": "2020-01-01T00:00:00Z",
               "description": null,
               "organization": {
                 "slug": "xia",
                 "created_at": "2019-01-01T00:00:00Z",
                 "full_name": "Xia Lee",
                 "email": "xia@localhost.localdomain",
                 "phone": "555-555-5555",
                 "street_address": "350 Bay St.",
                 "locality": "San Francisco",
                 "region": "CA",
                 "postal_code": "94133",
                 "country": "US",
                 "default_timezone": "UTC",
                 "printable_name": "Xia Lee",
                 "is_provider": false,
                 "is_bulk_buyer": false,
                 "type": "personal",
                 "credentials": true,
                 "extra": null
               },
               "plan": {
                 "slug": "open-space",
                 "title": "Open Space",
                 "description": "open space desk",
                 "is_active": true,
                 "setup_amount": 0,
                 "period_amount": 17999,
                 "period_length": 1,
                 "interval": "monthly",
                 "advance_discount": 0,
                 "unit": "cad",
                 "organization": "cowork",
                 "renewal_type": "auto-renew",
                 "is_not_priced": false,
                 "created_at": "2019-01-01T00:00:00Z",
                 "skip_optin_on_grant": false,
                 "optin_on_request": false,
                 "extra": null
               },
               "auto_renew": true,
               "editable": true,
               "extra": null,
               "grant_key": null,
               "request_key": null
             }
        """
        return super(SubscriptionListCreateAPIView, self).post(
            request, *args, **kwargs)


class SubscriptionDetailAPIView(SubscriptionMixin, DestroyModelMixin,
                                RetrieveAPIView):
    """
    Retrieves a subscription

    Returns the subscription of {organization} to {subscribed_plan}.

    **Tags: subscriptions

    **Examples

    .. code-block:: http

        GET /api/profile/xia/subscriptions/open-space/ HTTP/1.1

    responds

    .. code-block:: json

        {
          "created_at": "2019-01-01T00:00:00Z",
          "ends_at": "2020-01-01T00:00:00Z",
          "description": null,
          "organization": {
            "slug": "xia",
            "created_at": "2019-01-01T00:00:00Z",
            "full_name": "Xia Lee",
            "email": "xia@localhost.localdomain",
            "phone": "555-555-5555",
            "street_address": "350 Bay St.",
            "locality": "San Francisco",
            "region": "CA",
            "postal_code": "94133",
            "country": "US",
            "default_timezone": "UTC",
            "printable_name": "Xia Lee",
            "is_provider": false,
            "is_bulk_buyer": false,
            "type": "personal",
            "credentials": true,
            "extra": null
          },
          "plan": {
            "slug": "open-space",
            "title": "Open Space",
            "description": "open space desk",
            "is_active": true,
            "setup_amount": 0,
            "period_amount": 17999,
            "period_length": 1,
            "interval": "monthly",
            "advance_discount": 0,
            "unit": "cad",
            "organization": "cowork",
            "renewal_type": "auto-renew",
            "is_not_priced": false,
            "created_at": "2019-01-01T00:00:00Z",
            "skip_optin_on_grant": false,
            "optin_on_request": false,
            "extra": null
          },
          "auto_renew": true,
          "editable": true,
          "extra": null,
          "grant_key": null,
          "request_key": null
        }
    """
    serializer_class = SubscriptionSerializer

    def delete(self, request, *args, **kwargs):
        """
        Unsubscribes

        Unsubscribes {organization} from {subscribed_plan}.

        **Tags: subscriptions

        **Examples

        .. code-block:: http

            DELETE /api/profile/xia/subscriptions/open-space/ HTTP/1.1
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


class PlanSubscriptionsAPIView(SubscriptionSmartListMixin,
                               PlanSubscribersQuerysetMixin,
                               OptinBase, ListCreateAPIView):
    """
    Lists subscriptions to a plan

    Returns a PAGE_SIZE records of subscriptions to {plan} provided by
    {organization}.

    **Tags: subscriptions

    **Examples

    .. code-block:: http

        GET /api/profile/cowork/plans/premium/subscriptions/ HTTP/1.1

    responds

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
    filter_backends = SubscriptionSmartListMixin.filter_backends + (
        DateRangeFilter,)

    def add_relations(self, organizations, user, ends_at=None):
        ends_at = datetime_or_now(ends_at)
        subscriptions = []
        created = False
        self.decorate_personal(organizations)
        for organization in organizations:
            # Be careful that `self.plan` must exist otherwise the API will
            # return a 404.
            # We do not use `Subscription.objects.active_for` here because
            # if the subscription was already created and the grant yet to be
            # accepted, we want to avoid creating a duplicate.
            subscription = Subscription.objects.filter(
                organization=organization, plan=self.plan,
                ends_at__gte=ends_at).order_by('ends_at').first()
            if subscription is None:
                subscription = Subscription.objects.new_instance(
                    organization, plan=self.plan)
                if not self.plan.skip_optin_on_grant:
                    subscription.grant_key = generate_random_slug()
                subscription.save()
                created = True
            else:
                # We set subscription.organization to the object that was
                # loaded and initialized with `is_personal` otherwise we
                # will use a shadow copy loaded through `subscription`
                # when we sent the serialized data back.
                subscription.organization = organization
            subscriptions += [subscription]
        return subscriptions, created

    @swagger_auto_schema(request_body=SubscriptionCreateSerializer,
        query_serializer=ForceSerializer)
    def post(self, request, *args, **kwargs):
        """
        Subscribes to a plan through the provider

        Subscribes a customer to the {plan} provided by {organization}.

        **Tags: subscriptions

        **Examples

        .. code-block:: http

            POST /api/profile/cowork/plans/premium/subscriptions/ HTTP/1.1

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

    def send_signals(self, relations, user, reason=None, invite=False):
        for subscription in relations:
            signals.subscription_grant_created.send(sender=__name__,
                subscription=subscription, reason=reason, invite=invite,
                request=self.request)

    def create(self, request, *args, **kwargs): #pylint:disable=unused-argument
        serializer = SubscriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_optin(serializer, request)


class PlanSubscriptionDetailAPIView(ProviderMixin, UpdateModelMixin,
                                    SubscriptionDetailAPIView):
    """
    Retrieves a subscription through the provider

    Returns the subscription of {subscriber} to {plan} from provider
    {organization}.

    **Tags: subscriptions

    **Examples

    .. code-block:: http

        GET /api/profile/cowork/plans/open-space/subscriptions/xia/ HTTP/1.1

    responds

    .. code-block:: json

        {
          "created_at": "2019-01-01T00:00:00Z",
          "ends_at": "2020-01-01T00:00:00Z",
          "description": null,
          "organization": {
            "slug": "xia",
            "created_at": "2019-01-01T00:00:00Z",
            "full_name": "Xia Lee",
            "email": "xia@localhost.localdomain",
            "phone": "555-555-5555",
            "street_address": "350 Bay St.",
            "locality": "San Francisco",
            "region": "CA",
            "postal_code": "94133",
            "country": "US",
            "default_timezone": "UTC",
            "printable_name": "Xia Lee",
            "is_provider": false,
            "is_bulk_buyer": false,
            "type": "personal",
            "credentials": true,
            "extra": null
          },
          "plan": {
            "slug": "open-space",
            "title": "Open Space",
            "description": "open space desk",
            "is_active": true,
            "setup_amount": 0,
            "period_amount": 17999,
            "period_length": 1,
            "interval": "monthly",
            "advance_discount": 0,
            "unit": "cad",
            "organization": "cowork",
            "renewal_type": "auto-renew",
            "is_not_priced": false,
            "created_at": "2019-01-01T00:00:00Z",
            "skip_optin_on_grant": false,
            "optin_on_request": false,
            "extra": null
          },
          "auto_renew": true,
          "editable": true,
          "extra": null,
          "grant_key": null,
          "request_key": null
        }
    """
    subscriber_url_kwarg = 'subscriber'
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        return super(PlanSubscriptionDetailAPIView, self).get_queryset().filter(
            plan__organization=self.provider)


    def delete(self, request, *args, **kwargs):
        """
        Unsubscribes through the provider

        Unsubscribes {subscriber} from {plan} provided by {organization}.

        **Tags: subscriptions

        **Examples

        .. code-block:: http

            DELETE /api/profile/cowork/plans/open-space/subscriptions/xia/\
 HTTP/1.1
        """
        return super(PlanSubscriptionDetailAPIView, self).delete(
            request, *args, **kwargs)


    def put(self, request, *args, **kwargs):
        """
        Updates a subscription through the provider

        Updates the subscription of {subscriber} to {plan} from provider
        {organization}.

        **Tags: subscriptions

        **Examples

        .. code-block:: http

            PUT /api/profile/cowork/plans/open-space/subscriptions/xia/ HTTP/1.1

        .. code-block:: json

             {
               "ends_at": "2020-01-01T00:00:00Z",
               "description": "extended after call with customer"
             }

        responds

        .. code-block:: json

             {
               "created_at": "2019-01-01T00:00:00Z",
               "ends_at": "2020-01-01T00:00:00Z",
               "description": null,
               "organization": {
                 "slug": "xia",
                 "created_at": "2019-01-01T00:00:00Z",
                 "full_name": "Xia Lee",
                 "email": "xia@localhost.localdomain",
                 "phone": "555-555-5555",
                 "street_address": "350 Bay St.",
                 "locality": "San Francisco",
                 "region": "CA",
                 "postal_code": "94133",
                 "country": "US",
                 "default_timezone": "UTC",
                 "printable_name": "Xia Lee",
                 "is_provider": false,
                 "is_bulk_buyer": false,
                 "type": "personal",
                 "credentials": true,
                 "extra": null
               },
               "plan": {
                 "slug": "open-space",
                 "title": "Open Space",
                 "description": "open space desk",
                 "is_active": true,
                 "setup_amount": 0,
                 "period_amount": 17999,
                 "period_length": 1,
                 "interval": "monthly",
                 "advance_discount": 0,
                 "unit": "cad",
                 "organization": "cowork",
                 "renewal_type": "auto-renew",
                 "is_not_priced": false,
                 "created_at": "2019-01-01T00:00:00Z",
                 "skip_optin_on_grant": false,
                 "optin_on_request": false,
                 "extra": null
               },
               "auto_renew": true,
               "editable": true,
               "extra": null,
               "grant_key": null,
               "request_key": null
             }
        """
        return super(PlanSubscriptionDetailAPIView, self).put(
            request, *args, **kwargs)


class ActiveSubscriptionBaseAPIView(SubscribedQuerysetMixin, ListAPIView):

    pass


class ActiveSubscriptionAPIView(SubscriptionSmartListMixin,
                                ActiveSubscriptionBaseAPIView):
    """
    Lists active subscriptions

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

    responds

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
    filter_backends = (SubscriptionSmartListMixin.filter_backends +
        (DateRangeFilter,))


class ChurnedSubscriptionBaseAPIView(ChurnedQuerysetMixin, ListAPIView):

    pass


class ChurnedSubscriptionAPIView(SubscriptionSmartListMixin,
                                 ChurnedSubscriptionBaseAPIView):
    """
    Lists churned subscriptions

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

    responds

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


class SubscriptionRequestAcceptAPIView(CreateAPIView):
    """
    Grants a subscription request

    Accepts a subscription request.

    **Tags: rbac

    **Examples

    .. code-block:: http

        POST /api/profile/xia/subscribers/accept\
/a00000d0a0000001234567890123456789012345 HTTP/1.1

    responds

    .. code-block:: json

        {
          "created_at": "2019-01-01T00:00:00Z",
          "ends_at": "2020-01-01T00:00:00Z",
          "description": null,
          "organization": {
            "slug": "xia",
            "created_at": "2019-01-01T00:00:00Z",
            "full_name": "Xia Lee",
            "email": "xia@localhost.localdomain",
            "phone": "555-555-5555",
            "street_address": "350 Bay St.",
            "locality": "San Francisco",
            "region": "CA",
            "postal_code": "94133",
            "country": "US",
            "default_timezone": "UTC",
            "printable_name": "Xia Lee",
            "is_provider": false,
            "is_bulk_buyer": false,
            "type": "personal",
            "credentials": true,
            "extra": null
          },
          "plan": {
            "slug": "open-space",
            "title": "Open Space",
            "description": "open space desk",
            "is_active": true,
            "setup_amount": 0,
            "period_amount": 17999,
            "period_length": 1,
            "interval": "monthly",
            "advance_discount": 0,
            "unit": "cad",
            "organization": "cowork",
            "renewal_type": "auto-renew",
            "is_not_priced": false,
            "created_at": "2019-01-01T00:00:00Z",
            "skip_optin_on_grant": false,
            "optin_on_request": false,
            "extra": null
          },
          "auto_renew": true,
          "editable": true,
          "extra": null,
          "grant_key": null,
          "request_key": null
        }
    """
    provider_url_kwarg = 'organization'
    serializer_class = SubscriptionSerializer

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
