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
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.db import transaction, IntegrityError
from django.db.models import F
from rest_framework import status
from rest_framework.generics import (ListAPIView, ListCreateAPIView,
    RetrieveUpdateDestroyAPIView)
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


class OrganizationQuerysetMixin(object):

    queryset = get_organization_model().objects.all()

    @staticmethod
    def as_organization(user):
        organization = get_organization_model()(
            slug=user.username, email=user.email,
            full_name=user.get_full_name(), created_at=user.date_joined)
        organization.user = user
        return organization

    @staticmethod
    def decorate_personal(page):
        # Adds a boolean `is_personal` if there exists a User such that
        # `Organization.slug == User.username`.
        # Implementation Note:
        # The SQL we wanted to generate looks like the following.
        #
        # SELECT slug,
        #   (Count(slug=username) > 0) AS is_personal
        #   (Count(slug=username
        #      AND NOT (password LIKE '!%')) > 0) AS credentials
        # FROM saas_organization LEFT OUTER JOIN (
        #   SELECT organization_id, username FROM auth_user INNER JOIN saas_role
        #   ON auth_user.id = saas_role.user_id) AS roles
        # ON saas_organization.id = roles.organization_id
        # GROUP BY saas_organization.id;
        #
        # I couldn't figure out a way to get Django ORM to do this. The closest
        # attempts was
        #    queryset = get_organization_model().objects.annotate(
        #        Count('role__user__username')).extra(
        #        select={'is_personal': "count(slug=username) > 0"})
        #
        # Unfortunately that adds `is_personal` and `credentials` to the GROUP
        # BY clause, which leads to an exception.
        #
        # The UNION implementation below cannot be furthered filtered
        # (https://docs.djangoproject.com/en/2.2/ref/models/querysets/#union)
        #personal_qs = get_organization_model().objects.filter(
        #    role__user__username=F('slug')).extra(select={'is_personal': 1,
        #    'credentials':
        #        "NOT (password LIKE '" + UNUSABLE_PASSWORD_PREFIX + "%%')"})
        #organization_qs = get_organization_model().objects.exclude(
        #    role__user__username=F('slug')).extra(select={'is_personal': 0,
        #    'credentials': 0})
        #queryset = personal_qs.union(organization_qs)
        #
        # A raw query cannot be furthered filtered either.
        records = page if isinstance(page, list) else [page]
        personal = dict(get_organization_model().objects.filter(
            pk__in=[profile.pk for profile in records if profile.pk],
            role__user__username=F('slug')).extra(select={
            'credentials': ("NOT (password LIKE '" + UNUSABLE_PASSWORD_PREFIX
            + "%%')")}).values_list('pk', 'credentials'))
        for profile in records:
            if profile.pk in personal:
                profile.is_personal = True
                profile.credentials = personal[profile.pk]
        return page


class OrganizationDetailAPIView(OrganizationMixin, OrganizationQuerysetMixin,
                                RetrieveUpdateDestroyAPIView):
    """
    Retrieves an organization, personal or user profile.

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
    serializer_class = OrganizationWithSubscriptionsSerializer
    user_model = get_user_model()

    def put(self, request, *args, **kwargs):
        """
        Updates an organization, personal or user profile.

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
        Deletes a profile.

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
        obj = super(OrganizationDetailAPIView, self).get_object()
        self.decorate_personal(obj)
        return obj

    def get_queryset(self):
        return super(OrganizationDetailAPIView,
            self).get_queryset().prefetch_related('subscriptions')

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


class OrganizationListAPIView(OrganizationSmartListMixin,
                              OrganizationQuerysetMixin, ListCreateAPIView):
    """
    Queries a page (``PAGE_SIZE`` records) of organization and user profiles.

    The queryset can be filtered for at least one field to match a search
    term (``q``).

    The queryset can be ordered by a field by adding an HTTP query parameter
    ``o=`` followed by the field name. A sequence of fields can be used
    to create a complete ordering by adding a sequence of ``o`` HTTP query
    parameters. To reverse the natural order of a field, prefix the field
    name by a minus (-) sign.

    **Tags: profile

    **Examples

    .. code-block:: http

        GET /api/profile/?o=created_at HTTP/1.1

    responds

    .. code-block:: json

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
        Creates an organization, personal or user profile.

        **Examples

        .. code-block:: http

            POST /api/profile/ HTTP/1.1

        .. code-block:: json

            {
              "email": "xia@locahost.localdomain",
              "full_name": "Xia Lee"
            }
        """
        return self.create(request, *args, **kwargs)

    def paginate_queryset(self, queryset):
        page = super(OrganizationListAPIView, self).paginate_queryset(queryset)
        page = self.decorate_personal(page)
        return page

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
