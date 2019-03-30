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

import re

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model, logout as auth_logout
from django.db import transaction, IntegrityError
from django.db.models import Count, Q
from django.http import Http404
from rest_framework import filters, status
from rest_framework.settings import api_settings
from rest_framework.generics import (get_object_or_404, ListAPIView,
    ListCreateAPIView, RetrieveUpdateDestroyAPIView)
from rest_framework.response import Response

from .serializers import (CreateOrganizationSerializer,
    OrganizationSerializer, OrganizationWithSubscriptionsSerializer)
from .. import signals
from ..decorators import _valid_manager
from ..docs import swagger_auto_schema
from ..mixins import (OrganizationMixin, OrganizationSmartListMixin,
    ProviderMixin)
from ..models import get_broker
from ..utils import (full_name_natural_split, get_organization_model,
    handle_uniq_error)


#pylint: disable=no-init
#pylint: disable=old-style-class

def get_order_func(fields):
    """
    Builds a lambda function that can be used to order two records
    based on a sequence of fields.

    When a field name is preceeded by '-', the order is reversed.
    """
    if len(fields) == 1:
        if fields[0].startswith('-'):
            field_name = fields[0][1:]
            return lambda left, right: (
                getattr(left, field_name) > getattr(right, field_name))
        field_name = fields[0]
        return lambda left, right: (
            getattr(left, field_name) < getattr(right, field_name))
    if fields[0].startswith('-'):
        field_name = fields[0][1:]
        return lambda left, right: (
            getattr(left, field_name) > getattr(right, field_name) or
            get_order_func(fields[1:])(left, right))
    field_name = fields[0]
    return lambda left, right: (
        getattr(left, field_name) < getattr(right, field_name) or
        get_order_func(fields[1:])(left, right))


class OrganizationDetailAPIView(OrganizationMixin,
                                RetrieveUpdateDestroyAPIView):
    """
    Retrieves profile information on an ``Organization``.

    **Tags: profile

    **Examples

    .. code-block:: http

        GET /api/profile/xia/ HTTP/1.1

    responds

    .. code-block:: json

        {
            "created_at": "2018-01-01T00:00:00Z",
            "email": "xia@locahost.localdomain",
            "full_name": "Xia Lee",
            "printable_name": "Xia Lee",
            "slug": "xia",
            "subscriptions": [
                {
                    "created_at": "2018-01-01T00:00:00Z",
                    "ends_at": "2019-01-01T00:00:00Z",
                    "plan": "open-space",
                    "auto_renew": true
                }
            ]
        }
    """
    lookup_field = 'slug'
    lookup_url_kwarg = 'organization'
    queryset = get_organization_model().objects.all().prefetch_related(
        'subscriptions')
    serializer_class = OrganizationWithSubscriptionsSerializer
    user_model = get_user_model()

    def put(self, request, *args, **kwargs):
        """
        Updates profile information for an ``Organization``

        **Examples

        .. code-block:: http

            PUT /api/profile/xia/ HTTP/1.1

        .. code-block:: json

            {
              "email": "xia@locahost.localdomain",
              "full_name": "Xia Lee"
            }
        """
        return self.update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        """
        Deletes an `Organization``.

        We anonymize the organization instead of purely deleting
        it from the database because we don't want to loose history
        on subscriptions and transactions.

        **Tags: profile

        **Examples

        .. code-block:: http

            DELETE /api/profile/xia/ HTTP/1.1
        """
        return self.destroy(request, *args, **kwargs)

    def get_object(self):
        try:
            obj = super(OrganizationDetailAPIView, self).get_object()
        except Http404:
            # We might still have a `User` model that matches.
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            filter_kwargs = {'username': self.kwargs[lookup_url_kwarg]}
            user = get_object_or_404(self.user_model.objects.filter(
                is_active=True), **filter_kwargs)
            obj = self.as_organization(user)
        return obj

    def perform_update(self, serializer):
        is_provider = serializer.instance.is_provider
        if _valid_manager(self.request, [get_broker()]):
            is_provider = serializer.validated_data.get(
                'is_provider', is_provider)
        changes = serializer.instance.get_changes(serializer.validated_data)
        user = serializer.instance.attached_user()
        if user:
            user.username = serializer.validated_data.get(
                'slug', user.username)
        serializer.instance.slug = serializer.validated_data.get(
            'slug', serializer.instance.slug)
        serializer.save(is_provider=is_provider)
        signals.organization_updated.send(sender=__name__,
                organization=serializer.instance, changes=changes,
                user=self.request.user)

    def destroy(self, request, *args, **kwargs): #pylint:disable=unused-argument
        """
        Archive the organization. We don't to loose the subscriptions
        and transactions history.
        """
        obj = self.get_object()
        user = obj.attached_user()
        email = obj.email
        slug = '_archive_%d' % obj.id
        look = re.match(r'.*(@\S+)', django_settings.DEFAULT_FROM_EMAIL)
        if look:
            email = '%s+%d%s' % (obj.slug, obj.id, look.group(1))
        with transaction.atomic():
            if user:
                user.is_active = False
                user.username = slug
                user.email = email
                user.save()
            obj.slug = slug
            obj.email = email
            obj.is_active = False
            obj.save()
            if request.user == user:
                auth_logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationQuerysetMixin(object):

    @staticmethod
    def get_queryset():
        # Adds a boolean `is_personal` if there exists a User such that
        # `Organization.slug == User.username`.
        queryset = get_organization_model().objects.annotate(
            nb_roles=Count('role__user__username')).extra(
                select={'is_personal': "slug = username"})
        return queryset


class OrganizationListAPIView(OrganizationSmartListMixin,
                              OrganizationQuerysetMixin, ListCreateAPIView):
    """
    Queries all ``Organization``.

    **Tags: profile

    **Examples

    .. code-block:: http

        GET /api/profile/?o=created_at&ot=desc HTTP/1.1

    .. code-block:: http

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
    user_model = get_user_model()

    @swagger_auto_schema(request_body=CreateOrganizationSerializer)
    def post(self, request, *args, **kwargs):
        """
        Creates an``Organization``

        **Examples

        .. code-block:: http

            POST /api/profile/xia/ HTTP/1.1

        .. code-block:: json

            {
              "email": "xia@locahost.localdomain",
              "full_name": "Xia Lee"
            }
        """
        return self.create(request, *args, **kwargs)

    @staticmethod
    def as_organization(user):
        return get_organization_model()(slug=user.username, email=user.email,
            full_name=user.get_full_name(), created_at=user.date_joined)

    def get_users_queryset(self):
        # All users not already picked up as an Organization.
        return self.user_model.objects.filter(is_active=True).exclude(
            pk__in=self.user_model.objects.extra(
                tables=['saas_organization'],
                where=["username = slug"]).values('pk'))

    def list(self, request, *args, **kwargs):
        #pylint:disable=too-many-locals
        organizations_queryset = self.filter_queryset(self.get_queryset())
        organizations_page = self.paginate_queryset(organizations_queryset)
        # XXX When we use a `rest_framework.PageNumberPagination`,
        # it will hold a reference to the page created by a `DjangoPaginator`.
        # The `LimitOffsetPagination` paginator holds its own count.
        if hasattr(self.paginator, 'page'):
            organizations_count = self.paginator.page.paginator.count
        else:
            organizations_count = self.paginator.count

        users_queryset = self.filter_queryset(self.get_users_queryset())
        users_page = self.paginate_queryset(users_queryset)
        # Since we run a second `paginate_queryset`, the paginator.count
        # is not the number of users.
        if hasattr(self.paginator, 'page'):
            self.paginator.page.paginator.count += organizations_count
        else:
            self.paginator.count += organizations_count

        order_func = get_order_func(filters.OrderingFilter().get_ordering(
            self.request, users_queryset, self))

        # XXX merge `users_page` into page.
        page = []
        user = None
        organization = None
        users_iterator = iter(users_page)
        organizations_iterator = iter(organizations_page)
        try:
            organization = next(organizations_iterator)
        except StopIteration:
            pass
        try:
            user = self.as_organization(next(users_iterator))
        except StopIteration:
            pass
        try:
            while organization and user:
                if order_func(organization, user):
                    page += [organization]
                    organization = None
                    organization = next(organizations_iterator)
                elif order_func(user, organization):
                    page += [user]
                    user = None
                    user = self.as_organization(next(users_iterator))
                else:
                    page += [organization]
                    organization = None
                    organization = next(organizations_iterator)
                    page += [user]
                    user = None
                    user = self.as_organization(next(users_iterator))
        except StopIteration:
            pass
        try:
            while organization:
                page += [organization]
                organization = next(organizations_iterator)
        except StopIteration:
            pass
        try:
            while user:
                page += [user]
                user = self.as_organization(next(users_iterator))
        except StopIteration:
            pass

        # XXX It could be faster to stop previous loops early but it is not
        # clear. The extra check at each iteration might in fact be slower.
        page = page[:api_settings.PAGE_SIZE]

        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = CreateOrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # creates profile
        full_name = serializer.validated_data.get('full_name')
        email = serializer.validated_data.get('email')
        organization_model = get_organization_model()
        organization = organization_model(
            full_name=full_name, email=email,
            slug=serializer.validated_data.get('slug', None),
            default_timezone=serializer.validated_data.get(
                'default_timezone', ""),
            phone=serializer.validated_data.get('phone', ""),
            street_address=serializer.validated_data.get('street_address', ""),
            locality=serializer.validated_data.get('locality', ""),
            region=serializer.validated_data.get('region', ""),
            postal_code=serializer.validated_data.get('postal_code', ""),
            country=serializer.validated_data.get('country', ""),
            extra=serializer.validated_data.get('extra'))
        with transaction.atomic():
            try:
                organization.save()
                organization.is_personal = (
                    serializer.validated_data.get('type') == 'personal')
                if organization.is_personal:
                    first_name, mid, last_name = full_name_natural_split(
                        full_name)
                    user = self.user_model.objects.create_user(
                        username=organization.slug,
                        email=email, first_name=first_name, last_name=last_name)
                    organization.add_manager(
                        user, request_user=self.request.user)
            except IntegrityError as err:
                handle_uniq_error(err)

        # returns created profile
        serializer = self.get_serializer(instance=organization)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data,
            status=status.HTTP_201_CREATED, headers=headers)


class SubscribersQuerysetMixin(ProviderMixin):

    def get_queryset(self):
        queryset = get_organization_model().objects.filter(
            subscriptions__organization=self.provider)
        return queryset


class SubscribersAPIView(OrganizationSmartListMixin,
                         SubscribersQuerysetMixin, ListAPIView):
    """
    List all ``Organization`` which have or had a subscription to a plan
    provided by ``:organization``.

    **Tags: subscriptions

    **Examples

    .. code-block:: http

        GET /api/profile/cowork/subscribers/?o=created_at&ot=desc HTTP/1.1

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
    serializer_class = OrganizationSerializer
