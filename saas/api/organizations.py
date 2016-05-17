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

import re

from django.conf import settings as django_settings
from django.contrib.auth import logout as auth_logout
from django.db import transaction
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response

from .serializers import (
    OrganizationSerializer, OrganizationWithSubscriptionsSerializer)
from ..mixins import (OrganizationMixin, OrganizationSmartListMixin,
    ProviderMixin)
from ..models import Organization

#pylint: disable=no-init
#pylint: disable=old-style-class

class OrganizationDetailAPIView(OrganizationMixin,
                                RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete an ``Organization``.

    **Example response**:

    .. sourcecode:: http

        {
            "slug": "xia",
            "full_name": "Xia Lee",
            "created_at": "2016-01-14T23:16:55Z",
            "subscriptions": [
                {
                    "created_at": "2016-01-14T23:16:55Z",
                    "ends_at": "2017-01-14T23:16:55Z",
                    "plan": "open-space",
                    "auto_renew": true
                }
            ]
        }

    On ``DELETE``, we anonymize the organization instead of purely deleting
    it from the database because we don't want to loose history on subscriptions
    and transactions.
    """

    queryset = Organization.objects.all()
    serializer_class = OrganizationWithSubscriptionsSerializer

    def get_object(self):
        return self.organization

    def destroy(self, request, *args, **kwargs): #pylint:disable=unused-argument
        """
        Archive the organization. We don't to loose the subscriptions
        and transactions history.
        """
        obj = self.get_object()
        manager = self.attached_manager(obj)
        email = obj.email
        slug = '_archive_%d' % obj.id
        look = re.match(r'.*(@\S+)', django_settings.DEFAULT_FROM_EMAIL)
        if look:
            email = '%s+%d%s' % (obj.slug, obj.id, look.group(1))
        with transaction.atomic():
            if manager:
                manager.is_active = False
                manager.username = slug
                manager.email = email
                manager.save()
            obj.slug = slug
            obj.email = email
            obj.is_active = False
            obj.save()
            if request.user == manager:
                auth_logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationQuerysetMixin(object):

    @staticmethod
    def get_queryset():
        return Organization.objects.all()


class OrganizationListAPIView(OrganizationSmartListMixin,
                              OrganizationQuerysetMixin, ListAPIView):
    """
    GET queries all ``Organization``.

    .. autoclass:: saas.mixins.OrganizationSmartListMixin

    **Example request**:

    .. sourcecode:: http

        GET /api/profile/?o=created_at&ot=desc

    **Example response**:

    .. sourcecode:: http

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [{
                "slug": "xia",
                "full_name": "Xia Lee",
                "printable_name": "Xia Lee",
                "created_at": "2016-01-14T23:16:55Z"
            }]
        }
    """
    serializer_class = OrganizationSerializer


class SubscribersQuerysetMixin(ProviderMixin):

    def get_queryset(self):
        queryset = Organization.objects.filter(
            subscriptions__organization=self.provider)
        return queryset


class SubscribersAPIView(OrganizationSmartListMixin,
                         SubscribersQuerysetMixin, ListAPIView):
    """
    List all ``Organization`` which have or had a subscription to a plan
    provided by ``:organization``.

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

        GET /api/profile/:organization/subscribers/?o=created_at&ot=desc

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
    """
    serializer_class = OrganizationSerializer
