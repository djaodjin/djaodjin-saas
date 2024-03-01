# Copyright (c) 2023, DjaoDjin inc.
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

from django.http import Http404
from rest_framework import status
from rest_framework.generics import (get_object_or_404, GenericAPIView,
    ListAPIView, RetrieveUpdateDestroyAPIView)
from rest_framework.response import Response

from ..compat import gettext_lazy as _
from ..decorators import _valid_manager
from ..docs import OpenApiResponse, extend_schema
from ..filters import (ActiveInPeriodFilter, ChurnedInPeriodFilter,
    IntersectPeriodFilter)
from ..mixins import (PlanProvidedSubscriptionsMixin,
    ProvidedSubscriptionsMixin, SubscribedSubscriptionsMixin,
    SubscriptionSmartListMixin)
from .. import settings, signals
from ..models import Subscription
from ..utils import generate_random_slug, datetime_or_now
from .roles import ListOptinAPIView
from .serializers import (QueryParamForceSerializer,
    ProvidedSubscriptionSerializer, ProvidedSubscriptionCreateSerializer,
    ProvidedSubscriptionDetailSerializer,SubscribedSubscriptionSerializer)


LOGGER = logging.getLogger(__name__)


class ActiveSubscribedSubscriptionsMixin(SubscriptionSmartListMixin,
                                         SubscribedSubscriptionsMixin):

    filter_backends = SubscriptionSmartListMixin.filter_backends + (
        ActiveInPeriodFilter,)


class SubscribedSubscriptionListAPIView(ActiveSubscribedSubscriptionsMixin,
                                        ListAPIView):
    """
    Lists present subscriptions

    Returns a list of {{PAGE_SIZE}} subscriptions for subscriber {profile}
    whose renewal date is later than the time at which the API call was made.

    The queryset can be filtered such that each subscription initial start
    date is greater than the ``start_at`` query parameter.

    The queryset can be filtered for at least one field to match a search
    term (``q``).

    Returned results can be ordered by natural fields (``o``) in either
    ascending or descending order by using the minus sign ('-') in front
    of the ordering field name.

    The API is typically used within an HTML
    `subscriptions page </docs/guides/themes/#dashboard_profile_subscriptions>`_
    as present in the default theme.

    **Tags**: subscriptions, subscriber, subscriptionmodel

    **Examples**

    .. code-block:: http

        GET /api/profile/xia/subscriptions?o=created_at&ot=desc HTTP/1.1

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
                    "profile": {
                        "slug": "xia",
                        "printable_name": "Xia Lee",
                        "picture": null,
                        "type": "personal",
                        "credentials": true
                    },
                    "plan": {
                        "slug": "open-space",
                        "title": "Open Space"
                    },
                    "auto_renew": true,
                    "app_url": "http://localhost:8020/app/xia/open-space/"
                }
            ]
        }
    """
    serializer_class = SubscribedSubscriptionSerializer

    # No POST. We are talking about a subscriber Organization here.


class ExpiredSubscriptionsMixin(SubscriptionSmartListMixin,
                                SubscribedSubscriptionsMixin):

    filter_backends = SubscriptionSmartListMixin.filter_backends + (
        ChurnedInPeriodFilter,)


class ExpiredSubscriptionsAPIView(ExpiredSubscriptionsMixin, ListAPIView):
    """
    Lists expired subscriptions

    Returns a list of {{PAGE_SIZE}} subscriptions for subscriber {profile}
    which have ended already the time at which the API call was made.

    Optionally by defining either ``start_at``, ``ends_at`` , or both,
    it is possible to find subscriptions which have expired within
    a specified period.

    The queryset can be filtered for at least one field to match a search
    term (``q``).

    Returned results can be ordered by natural fields (``o``) in either
    ascending or descending order by using the minus sign ('-') in front
    of the ordering field name.

    The API is typically used within an HTML
    `subscriptions page </docs/guides/themes/#dashboard_profile_subscriptions>`_
    as present in the default theme.

    **Tags**: subscriptions, subscriber, subscriptionmodel

    **Examples**

    .. code-block:: http

        GET /api/profile/xia/subscriptions/expired?o=created_at&ot=desc HTTP/1.1

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
                    "profile": {
                        "slug": "xia",
                        "printable_name": "Xia Lee",
                        "picture": null,
                        "type": "personal",
                        "credentials": true
                    },
                    "plan": {
                        "slug": "open-space",
                        "title": "Open Space"
                    },
                    "auto_renew": true,
                    "app_url": "http://localhost:8020/app/xia/open-space/"
                }
            ]
        }
    """
    serializer_class = SubscribedSubscriptionSerializer


class SubscriptionDetailMixin(object):

    def get_object(self):
        queryset = self.get_queryset()
        obj = queryset.filter(
            ends_at__gt=datetime_or_now()).order_by('ends_at').first()
        if not obj:
            raise Http404(_("cannot find active subscription to"\
                " %(plan)s for %(organization)s") % {
                'plan': self.kwargs.get('plan', self.kwargs.get(
                    'subscribed_plan', None)),
                'organization': self.kwargs.get(self.subscriber_url_kwarg)})
        self.decorate_personal(obj.organization)
        return obj

    def perform_update(self, serializer):
        if not _valid_manager(
                self.request, [serializer.instance.plan.organization]):
            serializer.validated_data['created_at'] \
                = serializer.instance.created_at
            serializer.validated_data['ends_at'] = serializer.instance.ends_at
        super(SubscriptionDetailMixin, self).perform_update(serializer)

    def destroy(self, request, *args, **kwargs):
        #pylint:disable=unused-argument
        at_time = datetime_or_now()
        queryset = self.get_queryset().filter(ends_at__gt=at_time)
        queryset.unsubscribe(at_time=at_time)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SubscriptionDetailAPIView(SubscriptionDetailMixin,
                                SubscribedSubscriptionsMixin,
                                RetrieveUpdateDestroyAPIView):
    """
    Retrieves a subscriber subscription

    Returns a subscription to plan {subscribed_plan} for the specified
    subscriber.

    **Tags**: subscriptions, subscriber, subscriptionmodel

    **Examples**

    .. code-block:: http

        GET /api/profile/xia/subscriptions/open-space HTTP/1.1

    responds

    .. code-block:: json

        {
          "created_at": "2019-01-01T00:00:00Z",
          "ends_at": "2020-01-01T00:00:00Z",
          "description": null,
          "profile": {
              "slug": "xia",
              "printable_name": "Xia Lee",
              "picture": null,
              "type": "personal",
              "credentials": true
          },
          "plan": {
            "slug": "open-space",
            "title": "Open Space"
          },
          "auto_renew": true,
          "app_url": "http://localhost:8020/app/xia/open-space/",
          "editable": true,
          "extra": null,
          "grant_key": null,
          "request_key": null
        }
    """
    serializer_class = SubscribedSubscriptionSerializer
    plan_url_kwarg = 'subscribed_plan'

    def get_queryset(self):
        queryset = super(SubscriptionDetailAPIView, self).get_queryset().filter(
            plan__slug=self.kwargs.get(self.plan_url_kwarg))
        return queryset

    def put(self, request, *args, **kwargs):
        """
        Unsubscribes  at a future date

        Unsubscribes a specified subscriber from a plan {subscribed_plan}
        at a future date.

        The API is typically used within an HTML
        `subscribers page </docs/guides/themes/#dashboard_profile_subscribers>`_
        as present in the default theme.

        **Tags**: subscriptions, subscriber, subscriptionmodel

        **Examples**

        .. code-block:: http

            PUT /api/profile/xia/subscriptions/open-space HTTP/1.1

        .. code-block:: json

            {
              "ends_at": "2020-01-01T00:00:00Z"
            }

        responds

        .. code-block:: json

            {
              "created_at": "2019-01-01T00:00:00Z",
              "ends_at": "2020-01-01T00:00:00Z",
              "description": null,
              "profile": {
                  "slug": "xia",
                  "printable_name": "Xia Lee",
                  "picture": null,
                  "type": "personal",
                  "credentials": true
              },
              "plan": {
                "slug": "open-space",
                "title": "Open Space"
              },
              "auto_renew": true,
              "editable": true,
              "extra": null,
              "grant_key": null,
              "request_key": null
            }

        """
        return super(SubscriptionDetailAPIView, self).put(
            request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        """
        Unsubscribes now

        Unsubscribes a specified subscriber from a plan {subscribed_plan}.

        The API is typically used within an HTML
        `subscribers page </docs/guides/themes/#dashboard_profile_subscribers>`_
        as present in the default theme.

        **Tags**: subscriptions, subscriber, subscriptionmodel

        **Examples**

        .. code-block:: http

            DELETE /api/profile/xia/subscriptions/open-space HTTP/1.1
        """
        return super(SubscriptionDetailAPIView, self).delete(
            request, *args, **kwargs)


class PlanSubscriptionDetailAPIView(SubscriptionDetailMixin,
                                    PlanProvidedSubscriptionsMixin,
                                    RetrieveUpdateDestroyAPIView):
    """
    Retrieves a plan subscription

    Returns the subscription of {subscriber} to a plan {plan}
    of the specified provider.

    **Tags**: subscriptions, provider, subscriptionmodel

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/plans/open-space/subscriptions/xia HTTP/1.1

    responds

    .. code-block:: json

        {
          "created_at": "2019-01-01T00:00:00Z",
          "ends_at": "2020-01-01T00:00:00Z",
          "profile": {
              "slug": "xia",
              "printable_name": "Xia Lee",
              "picture": null,
              "type": "personal",
              "credentials": true
          },
          "plan": {
            "slug": "open-space",
            "title": "Open Space"
          },
          "description": null,
          "auto_renew": true,
          "extra": null,
          "grant_key": null,
          "request_key": null
        }
    """
    subscriber_url_kwarg = 'subscriber'
    serializer_class = ProvidedSubscriptionSerializer

    def get_queryset(self):
        queryset = super(
            PlanSubscriptionDetailAPIView, self).get_queryset().filter(
                organization__slug=self.kwargs.get(self.subscriber_url_kwarg))
        return queryset

    def delete(self, request, *args, **kwargs):
        """
        Cancels subscription

        Provider cancels a {subscriber}'s subscription to a plan {plan},
        effective at the time the API is called.


        **Tags**: subscriptions, provider, subscriptionmodel

        **Examples**

        .. code-block:: http

            DELETE /api/profile/cowork/plans/open-space/subscriptions/xia HTTP/1.1
        """
        return super(PlanSubscriptionDetailAPIView, self).delete(
            request, *args, **kwargs)


    def put(self, request, *args, **kwargs):
        """
        Updates a plan subscription

        Updates the subscription of {subscriber} to a plan {plan}
        of the specified provider.

        **Tags**: subscriptions, provider, subscriptionmodel

        **Examples**

        .. code-block:: http

            PUT /api/profile/cowork/plans/open-space/subscriptions/xia HTTP/1.1

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
                "profile": {
                    "slug": "xia",
                    "printable_name": "Xia Lee",
                    "picture": null,
                    "type": "personal",
                    "credentials": true
                },
                "plan": {
                    "slug": "open-space",
                    "title": "Open Space"
                },
                "description": null,
                "auto_renew": true,
                "extra": null,
                "grant_key": null,
                "request_key": null
             }
        """
        return super(PlanSubscriptionDetailAPIView, self).put(
            request, *args, **kwargs)


class PlanAllSubscribersBaseAPIView(PlanProvidedSubscriptionsMixin,
                                    ListAPIView):
    pass

class PlanAllSubscribersAPIView(SubscriptionSmartListMixin,
                                PlanAllSubscribersBaseAPIView):
    """
    Lists plan subscriptions

    Returns a list of {{PAGE_SIZE}} subscriptions to a plan {plan}
    of the provider {profile}.

    The queryset can be filtered for at least one field to match a search
    term (``q``) and/or intersects a period (``start_at``, ``ends_at``).

    Returned results can be ordered by natural fields (``o``) in either
    ascending or descending order by using the minus sign ('-') in front
    of the ordering field name.

    **Tags**: subscriptions, list, provider, subscriptionmodel

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/plans/premium/subscriptions/all HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [{
                "slug": "xia",
                "full_name": "Xia Lee",
                "created_at": "2016-01-14T23:16:55Z",
                "ends_at": "2017-01-14T23:16:55Z"
            }]
        }
    """
    serializer_class = ProvidedSubscriptionSerializer
    filter_backends = SubscriptionSmartListMixin.filter_backends + (
        IntersectPeriodFilter,)


class PlanActiveSubscribersBaseAPIView(PlanProvidedSubscriptionsMixin,
                                       ListOptinAPIView):
    pass


class PlanActiveSubscribersAPIView(SubscriptionSmartListMixin,
                                   PlanActiveSubscribersBaseAPIView):
    """
    Lists plan active subscriptions

    Returns a list of {{PAGE_SIZE}} subscriptions to a {plan}
    of the provider {profile} whose renewal date is later than the time
    at which the API call was made.

    Optionnaly when an ``start_at`` query parameter is specified,
    the returned queryset is filtered such that each subscription
    start date (i.e. ``created_at`` field) is greater than ``start_at``.
    Using the ``start_at`` query parameter, it is effectively possible
    to construct cohorts of active subscribers by period of initial
    subscription.

    The queryset can be filtered for at least one field to match a search
    term (``q``).

    Returned results can be ordered by natural fields (``o``) in either
    ascending or descending order by using the minus sign ('-') in front
    of the ordering field name.

    The API is typically used within an HTML
    `subscribers page </docs/guides/themes/#dashboard_profile_subscribers>`_
    as present in the default theme.

    **Tags**: subscriptions, list, provider, subscriptionmodel

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/plans/open-space/subscriptions?o=created_at&ot=desc HTTP/1.1

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
                    "profile": {
                        "slug": "xia",
                        "printable_name": "Xia Lee",
                        "type": "personal",
                        "credentials": true
                    },
                    "plan": {
                        "slug": "open-space",
                        "title": "Open Space"
                    },
                    "auto_renew": true
                }
            ]
        }
    """
    serializer_class = ProvidedSubscriptionDetailSerializer
    filter_backends = SubscriptionSmartListMixin.filter_backends + (
        ActiveInPeriodFilter,)

    def get_serializer_class(self):
        if self.request.method.lower() == 'post':
            return ProvidedSubscriptionCreateSerializer
        return super(PlanActiveSubscribersAPIView, self).get_serializer_class()

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

    @extend_schema(parameters=[QueryParamForceSerializer], responses={
      201: OpenApiResponse(ProvidedSubscriptionSerializer)})
    def post(self, request, *args, **kwargs):
        """
        Grants a subscription

        Subscribes a customer to the plan {plan} of the specified provider.

        **Tags**: subscriptions, provider, subscriptionmodel

        **Examples**

        .. code-block:: http

            POST /api/profile/cowork/plans/premium/subscriptions HTTP/1.1

        .. code-block:: json

            {
              "profile": {
                "slug": "xia",
                "full_name": "Xia Lee"
              }
            }

        responds

        .. code-block:: json

            {
              "created_at": "2016-01-14T23:16:55Z",
              "ends_at": "2017-01-14T23:16:55Z",
              "description": null,
              "profile": {
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
                "period_type": "monthly"
              },
              "auto_renew": true
            }
        """
        return super(PlanActiveSubscribersAPIView, self).post(
            request, *args, **kwargs)

    def send_signals(self, relations, user, reason=None, invite=False):
        for subscription in relations:
            signals.subscription_grant_created.send(sender=__name__,
                subscription=subscription, reason=reason, invite=invite,
                request=self.request)

    def create(self, request, *args, **kwargs): #pylint:disable=unused-argument
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_optin(serializer, request)


class PlanChurnedSubscribersBaseAPIView(PlanProvidedSubscriptionsMixin,
                                        ListAPIView):

    pass


class PlanChurnedSubscribersAPIView(SubscriptionSmartListMixin,
                                    PlanChurnedSubscribersBaseAPIView):
    """
    Lists plan churned subscriptions

    Returns a list of {{PAGE_SIZE}} subscriptions to a {plan}
    of the provider {profile} which have ended already at the time
    the API call was made.

    Optionally by defining either ``start_at``, ``ends_at`` , or both,
    it is possible to construct cohorts of subscribers that have churned
    within a period.

    The queryset can be filtered for at least one field to match a search
    term (``q``).

    Returned results can be ordered by natural fields (``o``) in either
    ascending or descending order by using the minus sign ('-') in front
    of the ordering field name.

    The API is typically used within an HTML
    `subscribers page </docs/guides/themes/#dashboard_profile_subscribers>`_
    as present in the default theme.

    **Tags**: subscriptions, list, provider, subscriptionmodel

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/plans/open-space/subscriptions/churned?o=created_at&ot=desc HTTP/1.1

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
                    "profile": {
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
                        "period_type": "monthly"
                    },
                    "auto_renew": true
                }
            ]
        }
    """
    serializer_class = ProvidedSubscriptionSerializer
    filter_backends = SubscriptionSmartListMixin.filter_backends + (
        ChurnedInPeriodFilter,)


class AllSubscriberSubscriptionsAPIView(SubscriptionSmartListMixin,
                                        ProvidedSubscriptionsMixin,
                                        ListAPIView):
    """
    Lists provider subscriptions

    Returns a list of {{PAGE_SIZE}} subscriber profiles which have or
    had a subscription to a plan of the specified provider.

    The queryset can be filtered for at least one field to match a search
    term (``q``)  and/or intersects a period (``start_at``, ``ends_at``).

    Returned results can be ordered by natural fields (``o``) in either
    ascending or descending order by using the minus sign ('-') in front
    of the ordering field name.

    **Tags**: subscriptions, list, provider, subscriptionmodel

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/subscribers/subscriptions/all?o=created_at&ot=desc HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2016-01-14T23:16:55Z",
                    "ends_at": "2022-01-14T23:16:55Z",
                    "description": null,
                    "profile": {
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
                        "period_type": "monthly"
                    },
                    "auto_renew": true
                }
            ]
        }
    """
    serializer_class = ProvidedSubscriptionSerializer
    filter_backends = SubscriptionSmartListMixin.filter_backends + (
        IntersectPeriodFilter,)



class ActiveSubscriberSubscriptionsMixin(SubscriptionSmartListMixin,
                             ProvidedSubscriptionsMixin):

    filter_backends = SubscriptionSmartListMixin.filter_backends + (
        ActiveInPeriodFilter,)


class ActiveSubscriberSubscriptionsAPIView(ActiveSubscriberSubscriptionsMixin,
                                           ListAPIView):
    """
    Lists provider active subscriptions

    Returns a list of {{PAGE_SIZE}} subscriptions whose renewal
    date is later than the time at which the API call was made,
    and the owner of the subscription plan is the specified provider
    {profile}.

    Optionnaly when an ``start_at`` query parameter is specified,
    the returned queryset is filtered such that each subscription
    start date (i.e. ``created_at`` field) is greater than ``start_at``.
    Using the ``start_at`` query parameter, it is effectively possible
    to construct cohorts of active subscribers by period of initial
    subscription.

    The queryset can be filtered for at least one field to match a search
    term (``q``).

    Returned results can be ordered by natural fields (``o``) in either
    ascending or descending order by using the minus sign ('-') in front
    of the ordering field name.

    The API is typically used within an HTML
    `subscribers page </docs/guides/themes/#dashboard_profile_subscribers>`_
    as present in the default theme.

    **Tags**: subscriptions, list, provider, subscriptionmodel

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/subscribers/subscriptions?o=created_at&ot=desc HTTP/1.1

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
                    "profile": {
                        "slug": "xia",
                        "printable_name": "Xia Lee",
                        "type": "personal",
                        "credentials": true
                    },
                    "plan": {
                        "slug": "open-space",
                        "title": "Open Space"
                    },
                    "auto_renew": true
                }
            ]
        }
    """
    serializer_class = ProvidedSubscriptionDetailSerializer


class ChurnedSubscribersMixin(SubscriptionSmartListMixin,
                              ProvidedSubscriptionsMixin):

    filter_backends = SubscriptionSmartListMixin.filter_backends + (
        ChurnedInPeriodFilter,)


class ChurnedSubscribersAPIView(ChurnedSubscribersMixin, ListAPIView):
    """
    Lists provider churned subscriptions

    Returns a list of {{PAGE_SIZE}} subscriptions which have ended already
    the time at which the API call was made, and the owner of the subscription
    plan is the specified provider {profile}.

    Optionally by defining either ``start_at``, ``ends_at`` , or both,
    it is possible to construct cohorts of subscribers that have churned
    within a period.

    The queryset can be filtered for at least one field to match a search
    term (``q``).

    Returned results can be ordered by natural fields (``o``) in either
    ascending or descending order by using the minus sign ('-') in front
    of the ordering field name.

    The API is typically used within an HTML
    `subscribers page </docs/guides/themes/#dashboard_profile_subscribers>`_
    as present in the default theme.

    **Tags**: subscriptions, list, provider, subscriptionmodel

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/subscribers/subscriptions/churned?o=created_at&ot=desc HTTP/1.1

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
                    "profile": {
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
                        "period_type": "monthly"
                    },
                    "auto_renew": true
                }
            ]
        }
    """
    serializer_class = ProvidedSubscriptionSerializer


class SubscriptionRequestAcceptAPIView(GenericAPIView):
    """
    Accepts a subscription request
    """
    provider_url_kwarg = settings.PROFILE_URL_KWARG
    serializer_class = ProvidedSubscriptionSerializer

    @property
    def subscription(self):
        #pylint:disable=attribute-defined-outside-init
        if not hasattr(self, '_subscription'):
            self._subscription = get_object_or_404(self.get_queryset(),
                request_key=self.kwargs.get('request_key'))
        return self._subscription

    def get_queryset(self):
        queryset = Subscription.objects.active_with(
            self.kwargs.get(self.provider_url_kwarg))
        # `ProvidedSubscriptionSerializer` derives from `SubscriptionSerializer`
        # thus will expand `organization` and `plan`.
        queryset = queryset.select_related('organization').select_related(
            'plan')
        return queryset

    @extend_schema(request=None, responses={
      200: OpenApiResponse(ProvidedSubscriptionSerializer)})
    def post(self, request, *args, **kwargs):
        """
        Grants a subscription request

        Accepts a subscription request identified by {request_key}.
        The subscription must be to a plan that belongs to the specified
        provider.

        **Tags**: rbac, provider, subscriptionmodel

        **Examples**

        .. code-block:: http

            POST /api/profile/cowork/subscribers/accept/\
a00000d0a0000001234567890123456789012345 HTTP/1.1

        responds

        .. code-block:: json

            {
              "created_at": "2019-01-01T00:00:00Z",
              "ends_at": "2020-01-01T00:00:00Z",
              "description": null,
              "profile": {
                "slug": "xia",
                "printable_name": "Xia Lee",
                "picture": null,
                "type": "personal",
                "credentials": true
              },
              "plan": {
                "slug": "open-space",
                "title": "Open Space"
              },
              "auto_renew": true,
              "extra": null,
              "grant_key": null,
              "request_key": null
            }
        """
        #pylint:disable=unused-argument
        request_key = self.kwargs.get('request_key')
        self.subscription.request_key = None
        LOGGER.info(
            "%s accepted subscription of %s to plan %s (request_key=%s)",
            self.request.user, self.subscription.organization,
            self.subscription.plan, request_key, extra={
                'request': self.request, 'event': 'accept',
                'user': str(self.request.user),
                'organization': str(self.subscription.organization),
                'plan': str(self.subscription.plan),
                'ends_at': str(self.subscription.ends_at),
                'request_key': request_key})
        signals.subscription_request_accepted.send(sender=__name__,
            subscription=self.subscription,
            request_key=request_key, request=self.request)
