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

from django.contrib.auth import get_user_model
from rest_framework.settings import api_settings
from rest_framework.generics import ListAPIView

from .organizations import OrganizationQuerysetMixin, OrganizationListAPIView
from .serializers import (OrganizationSerializer, UserSerializer)
from .. import filters
from ..mixins import (OrganizationSmartListMixin, UserSmartListMixin)


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


class AccountsSearchAPIView(OrganizationSmartListMixin,
                            OrganizationQuerysetMixin, ListAPIView):
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

        # XXX It could be faster to stop previous loops early but it is not
        # clear. The extra check at each iteration might in fact be slower.
        page = page[:api_settings.PAGE_SIZE]
        self.decorate_personal(page)

        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class ProfilesSearchAPIView(OrganizationListAPIView):

    pass


class UserQuerysetMixin(object):
    """
    All ``User``.
    """

    @staticmethod
    def get_queryset():
        return get_user_model().objects.all()


class UsersSearchAPIView(UserSmartListMixin, UserQuerysetMixin, ListAPIView):
    """
    Queries a page (``PAGE_SIZE`` records) of ``User``.

    The queryset can be filtered to a range of dates
    ([``start_at``, ``ends_at``]) and for at least one field to match a search
    term (``q``).

    Query results can be ordered by natural fields (``o``) in either ascending
    or descending order (``ot``).

    **Tags: profile

    **Examples

    .. code-block:: http

        GET  /api/users/?o=created_at&ot=desc HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "slug": "alice",
                    "email": "alice@djaodjin.com",
                    "full_name": "Alice Cooper",
                    "created_at": "2014-01-01T00:00:00Z"
                }
            ]
        }
    """
    serializer_class = UserSerializer
