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

from django.contrib.auth import get_user_model
from rest_framework import response as http, status
from rest_framework.generics import (ListAPIView, ListCreateAPIView,
    RetrieveAPIView)

from .serializers import (OrganizationSerializer, OrganizationCreateSerializer,
    OrganizationDetailSerializer)
from .. import filters, settings
from ..docs import OpenApiResponse, extend_schema
from ..mixins import (OrganizationCreateMixin, OrganizationSmartListMixin,
    OrganizationMixin, OrganizationDecorateMixin, UserSmartListMixin)
from ..pagination import TypeaheadPagination
from ..utils import get_organization_model, get_user_serializer


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
                (getattr(left, field_name) and getattr(right, field_name) and
                getattr(left, field_name) > getattr(right, field_name)))
        field_name = fields[0]
        return lambda left, right: (
            (getattr(left, field_name) and getattr(right, field_name) and
            getattr(left, field_name) < getattr(right, field_name)))
    if fields[0].startswith('-'):
        field_name = fields[0][1:]
        return lambda left, right: (
            (getattr(left, field_name) and getattr(right, field_name) and
            getattr(left, field_name) > getattr(right, field_name)) or
            get_order_func(fields[1:])(left, right))
    field_name = fields[0]
    return lambda left, right: (
        (getattr(left, field_name) and getattr(right, field_name) and
        getattr(left, field_name) < getattr(right, field_name)) or
        get_order_func(fields[1:])(left, right))


class OrganizationQuerysetMixin(OrganizationDecorateMixin):

    # Implementation Note: We are using this query in typeahead API calls.
    # Typeaheads are more often than not used to request/grant access to
    # a profile. We don't want to return profiles that cannot be notified
    # of a request.
    queryset = get_organization_model().objects.filter(
        is_active=True, email__isnull=False).exclude(email="")


class AccountsTypeaheadAPIView(OrganizationSmartListMixin,
                            OrganizationQuerysetMixin, ListAPIView):
    """
    Searches profile and user accounts

    Returns a list of {{MAX_TYPEAHEAD_CANDIDATES}} candidate profiles
    or user accounts based of a search criteria (``q``).

    The API is designed to be used in typeahead input fields. As such
    it only returns results when the number of candidates is less
    than {{MAX_TYPEAHEAD_CANDIDATES}}.

    If you need to list all profiles, please see
    `Lists billing profiles </docs/api/#listOrganization>`_

    The queryset can be further refined by a range of dates
    ([``start_at``, ``ends_at``]), and sorted on specific fields (``o``).

    The API is typically used in pages for the support team to quickly
    locate an account. For example, it is used within the HTML
    `provider dashboard page </docs/guides/themes/#dashboard_metrics_dashboard>`_
    as present in the default theme.

    **Tags**: list, profile, user

    **Examples**

    .. code-block:: http

        GET /api/accounts?q=xi HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "results": [{
                "slug": "xia",
                "printable_name": "Xia Lee",
                "picture": null,
                "type": "personal",
                "credentials": true
            }]
        }
    """
    serializer_class = OrganizationSerializer
    user_model = get_user_model()
    pagination_class = TypeaheadPagination

    def get_users_queryset(self):
        # All users not already picked up as an Organization.
        return self.user_model.objects.filter(is_active=True).exclude(
            pk__in=self.user_model.objects.extra(
                tables=['saas_organization'],
                where=["username = slug"]).values('pk'))

    def list(self, request, *args, **kwargs):
        #pylint:disable=too-many-locals,too-many-statements
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
            self.request, organizations_queryset, self))

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

        self.decorate_personal(page)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class ProfilesTypeaheadAPIView(OrganizationSmartListMixin,
                               OrganizationQuerysetMixin,
                               OrganizationCreateMixin, ListCreateAPIView):
    """
    Searches profiles

    Returns a list of {{MAX_TYPEAHEAD_CANDIDATES}} candidate profiles
    based of a search criteria (``q``).

    The API is designed to be used in typeahead input fields. As such
    it only returns results when the number of candidates is less
    than {{MAX_TYPEAHEAD_CANDIDATES}}.

    If you need to list all profiles, please see
    `Lists billing profiles </docs/api/#listOrganization>`_

    The queryset can be further refined by a range of dates
    ([``start_at``, ``ends_at``]), and sorted on specific fields (``o``).

    The API is typically used within an HTML
    `connected profiles page </docs/guides/themes/#dashboard_users_roles>`_
    as present in the default theme.

    **Tags**: list, profile, user

    **Examples**

    .. code-block:: http

        GET /api/accounts/profiles?q=xi HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "results": [{
                "slug": "xia",
                "printable_name": "Xia Lee",
                "picture": null,
                "type": "personal",
                "credentials": true
            }]
        }
    """
    serializer_class = OrganizationSerializer
    pagination_class = TypeaheadPagination

    def get_serializer_class(self):
        if self.request.method.lower() == 'post':
            return OrganizationCreateSerializer
        return super(ProfilesTypeaheadAPIView, self).get_serializer_class()

    @extend_schema(responses={
      201: OpenApiResponse(OrganizationDetailSerializer)})
    def post(self, request, *args, **kwargs):
        """
        Creates a shadow profile

        Creates a profile that is not associated to any user.

        **Tags**: profile, user

        **Examples**

        .. code-block:: http

            POST /api/accounts/profiles HTTP/1.1

        .. code-block:: json

            {
              "email": "xia@locahost.localdomain",
              "full_name": "Xia Lee",
              "type": "personal"
            }

        responds

        .. code-block:: json

            {
              "slug": "xia",
              "email": "xia@locahost.localdomain",
              "full_name": "Xia Lee",
              "printable_name": "Xia Lee",
              "type": "personal",
              "credentials": true,
              "default_timezone": "America/Los_Angeles",
              "phone": "",
              "street_address": "",
              "locality": "",
              "region": "",
              "postal_code": "",
              "country": "US",
              "is_bulk_buyer": false,
              "extra": null
            }

        """
        return self.create(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            if not page:
                # For B2B organizations, we often have a user e-mail address
                # and we want the profile using the same domain name.
                self.search_fields = self.__class__.search_fields + ('domain',)
                queryset = self.filter_queryset(self.get_queryset())
                page = self.paginate_queryset(queryset)

            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return http.Response(serializer.data)

    def paginate_queryset(self, queryset):
        page = super(ProfilesTypeaheadAPIView, self).paginate_queryset(queryset)
        page = self.decorate_personal(page)
        return page

    def create(self, request, *args, **kwargs):
        #pylint:disable=unused-argument
        serializer = OrganizationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # creates profile
        organization = self.create_organization(serializer.validated_data)
        self.decorate_personal(organization)

        # returns created profile
        serializer = OrganizationDetailSerializer(
            instance=organization,
            context=self.get_serializer_context())
        headers = self.get_success_headers(serializer.data)
        return http.Response(serializer.data,
            status=status.HTTP_201_CREATED, headers=headers)



class ProfileAPIView(OrganizationMixin, OrganizationDecorateMixin,
                     RetrieveAPIView):
    """
    Retrieves a profile summary

    While the `profiles typeahead <#listProfilesTypeahead>`_ API returns
    a list of profiles summary based on search criteria, if you already
    know the unique slug of a profile, you can get the same summary
    by using this API.

    **Tags**: profile, subscriber, profilemodel

    **Examples**

    .. code-block:: http

        GET /api/accounts/profiles/xia HTTP/1.1

    responds

    .. code-block:: json

        {
            "slug": "xia",
            "printable_name": "Xia Lee",
            "picture": null,
            "type": "organization",
            "credentials": true
        }
    """
    lookup_field = 'slug'
    lookup_url_kwarg = settings.PROFILE_URL_KWARG
    queryset = get_organization_model().objects.filter(is_active=True)
    serializer_class = OrganizationSerializer
    user_model = get_user_model()

    def get_object(self):
        obj = super(ProfileAPIView, self).get_object()
        self.decorate_personal(obj)
        return obj


class UserQuerysetMixin(object):
    """
    All ``User``.
    """

    @staticmethod
    def get_queryset():
        return get_user_model().objects.all()


class UsersTypeaheadAPIView(UserSmartListMixin, UserQuerysetMixin,
                            ListAPIView):
    """
    Searches users

    Returns a list of {{MAX_TYPEAHEAD_CANDIDATES}} candidate users
    based of a search criteria (``q``).

    The API is designed to be used in typeahead input fields. As such
    it only returns results when the number of candidates is less
    than {{MAX_TYPEAHEAD_CANDIDATES}}.

    If you need to list all users, please see
    `Lists user accounts </docs/api/#listUserListCreate>`_

    The queryset can be further refined by a range of dates
    ([``start_at``, ``ends_at``]), and sorted on specific fields (``o``).

    The API is typically used within an HTML
    `profile role page </docs/guides/themes/#dashboard_profile_roles>`_
    as present in the default theme.

    **Tags**: list, profile, user

    **Examples**

    .. code-block:: http

        GET  /api/accounts/users?q=ali HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "results": [
                {
                    "slug": "alice",
                    "username": "alice",
                    "printable_name": "Alice Cooper",
                    "picture": null
                }
            ]
        }
    """
    serializer_class = get_user_serializer()
    pagination_class = TypeaheadPagination
