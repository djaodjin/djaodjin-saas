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

from rest_framework.generics import (ListAPIView,
    ListCreateAPIView, RetrieveUpdateDestroyAPIView)

from ..mixins import (ChurnedQuerysetMixin, SubscriptionMixin,
    SubscriptionSmartListMixin, SubscribedQuerysetMixin)
from .serializers import SubscriptionSerializer

#pylint: disable=no-init,old-style-class


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

    def perform_destroy(self, instance):
        instance.unsubscribe_now()


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
