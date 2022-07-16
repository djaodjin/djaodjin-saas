# Copyright (c) 2022, DjaoDjin inc.
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

import hashlib, os, re

from dateutil.relativedelta import relativedelta
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model, logout as auth_logout
from django.db import transaction, IntegrityError
from rest_framework import parsers, status
from rest_framework.generics import (CreateAPIView, ListAPIView,
    RetrieveUpdateDestroyAPIView)
from rest_framework.response import Response

from .serializers import (OrganizationDetailSerializer,
    OrganizationWithSubscriptionsSerializer, UploadBlobSerializer)
from .. import settings, signals
from ..compat import force_str, gettext_lazy as _, urlparse, urlunparse
from ..decorators import _valid_manager
from ..filters import DateRangeFilter, OrderingFilter, SearchFilter
from ..mixins import (DateRangeContextMixin, OrganizationMixin,
    OrganizationSmartListMixin, ProviderMixin, OrganizationDecorateMixin)
from ..models import get_broker
from ..utils import (datetime_or_now, get_organization_model, get_role_model,
    get_role_serializer, handle_uniq_error, get_picture_storage)


class OrganizationQuerysetMixin(OrganizationDecorateMixin):

    queryset = get_organization_model().objects.all()


class OrganizationDetailAPIView(OrganizationMixin, OrganizationQuerysetMixin,
                                RetrieveUpdateDestroyAPIView):
    """
    Retrieves a billing profile

    The API is typically used within an HTML
    `contact information page </docs/themes/#dashboard_profile>`_
    as present in the default theme.

    **Tags**: profile, subscriber, profilemodel

    **Examples**

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
            "phone": "555-555-5555",
            "street_address": "185 Berry St #550",
            "locality": "San Francisco",
            "region": "CA",
            "postal_code": "",
            "country": "US",
            "default_timezone": "Europe/Kiev",
            "is_provider": false,
            "is_bulk_buyer": false,
            "type": "",
            "picture": "",
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
    lookup_url_kwarg = settings.PROFILE_URL_KWARG
    serializer_class = OrganizationWithSubscriptionsSerializer
    user_model = get_user_model()

    def put(self, request, *args, **kwargs):
        """
        Updates a billing profile

        The API is typically used within an HTML
        `contact information page </docs/themes/#dashboard_profile>`_
        as present in the default theme.

        **Tags**: profile, subscriber, profilemodel

        **Examples**

        .. code-block:: http

            PUT /api/profile/xia/ HTTP/1.1

        .. code-block:: json

            {
              "email": "xia@locahost.localdomain",
              "full_name": "Xia Lee"
            }

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
        return self.update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        """
        Deletes a billing profile

        We anonymize the profile instead of purely deleting
        it from the database because we don't want to loose history
        on subscriptions and transactions.

        The API is typically used within an HTML
        `contact information page </docs/themes/#dashboard_profile>`_
        as present in the default theme.

        **Tags**: profile, subscriber, profilemodel

        **Examples**

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
        try:
            serializer.save(is_provider=is_provider)
            serializer.instance.detail = _("Profile was updated.")
            signals.organization_updated.send(sender=__name__,
                organization=serializer.instance, changes=changes,
                user=self.request.user)
        except IntegrityError as err:
            handle_uniq_error(err)

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
            # Removes all roles on the organization such that the organization
            # is not picked up inadvertently.
            get_role_model().objects.filter(organization=obj).delete()
            obj.slug = slug
            obj.email = email
            obj.is_active = False
            obj.save()
            if request.user == user:
                auth_logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationPictureAPIView(OrganizationMixin, CreateAPIView):
    """
        Uploads a static asset file

        **Examples

        .. code-block:: http

            POST /api/profile/xia/picture/ HTTP/1.1

        responds

        .. code-block:: json

            {
              "location": "https://cowork.net/picture.jpg"
            }
    """
    parser_classes = (parsers.FormParser, parsers.MultiPartParser)
    serializer_class = UploadBlobSerializer

    def post(self, request, *args, **kwargs):
        #pylint:disable=unused-argument
        uploaded_file = request.data.get('file')
        if not uploaded_file:
            return Response({'detail': _("no location or file specified.")},
                status=status.HTTP_400_BAD_REQUEST)

        # tentatively extract file extension.
        parts = os.path.splitext(
            force_str(uploaded_file.name.replace('\\', '/')))
        ext = parts[-1].lower() if len(parts) > 1 else ""
        key_name = "%s%s" % (
            hashlib.sha256(uploaded_file.read()).hexdigest(), ext)
        default_storage = get_picture_storage(request)

        location = default_storage.url(
            default_storage.save(key_name, uploaded_file))
        # We are removing the query parameters, as they contain
        # signature information, not the relevant URL location.
        parts = urlparse(location)
        location = urlunparse((parts.scheme, parts.netloc, parts.path,
            "", "", ""))
        location = self.request.build_absolute_uri(location)

        self.organization.picture = location
        self.organization.save()
        return Response({'location': location}, status=status.HTTP_201_CREATED)


class OrganizationListAPIView(OrganizationSmartListMixin,
                              OrganizationQuerysetMixin,
                              ListAPIView):
    """
    Lists billing profiles

    Returns a list of {{PAGE_SIZE}} profile and user accounts.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    **Tags**: profile, broker, profilemodel

    **Examples**

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
                "email": "xia@localhost.localdomain",
                "printable_name": "Xia Lee",
                "created_at": "2016-01-14T23:16:55Z"
            }]
        }
    """
    serializer_class = OrganizationDetailSerializer
    user_model = get_user_model()

    def paginate_queryset(self, queryset):
        page = super(OrganizationListAPIView, self).paginate_queryset(queryset)
        page = self.decorate_personal(page)
        return page


class SubscribersQuerysetMixin(OrganizationDecorateMixin, ProviderMixin):

    def get_queryset(self):
        queryset = get_organization_model().objects.filter(
            subscribes_to__organization=self.provider)
        return queryset

    def paginate_queryset(self, queryset):
        page = super(SubscribersQuerysetMixin, self).paginate_queryset(queryset)
        page = self.decorate_personal(page)
        return page


class SubscribersAPIView(OrganizationSmartListMixin,
                         SubscribersQuerysetMixin, ListAPIView):
    """
    Lists subscribers for a provider

    Returns a list of {{PAGE_SIZE}} subscriber profiles which have or
    had a subscription to a plan provided by {organization}.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    **Tags**: subscriptions, provider, profilemodel

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/subscribers/?o=created_at&ot=desc HTTP/1.1

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
                "email": "xia@localhost.localdomain",
                "created_at": "2016-01-14T23:16:55Z",
                "ends_at": "2017-01-14T23:16:55Z"
                }
            ]
        }
    """
    serializer_class = OrganizationDetailSerializer


class EngagedSubscribersSmartListMixin(object):
    """
    reporting entities list which is also searchable and sortable.
    """
    date_field = 'user__last_login'

    search_fields = (
        'first_name',
        'last_name',
        'organization_full_name')

    ordering_fields = [('user__last_login', 'created_at'),
                       ('user__first_name', 'first_name'),
                       ('user__last_name', 'last_name'),
                       ('organization__full_name', 'organization_full_name')]

    ordering = ('created_at',)

    filter_backends = (DateRangeFilter, SearchFilter, OrderingFilter)


class EngagedSubscribersQuerysetMixin(DateRangeContextMixin,
                                     SubscribersQuerysetMixin):

    def get_queryset(self):
        filter_params = {}
        ends_at = datetime_or_now(self.ends_at)
        start_at = self.start_at
        if not start_at:
            start_at = ends_at - relativedelta(days=7)
        filter_params.update({
            'user__last_login__lt': ends_at,
            'user__last_login__gte': start_at
        })
        queryset = get_role_model().objects.filter(
            organization__in=get_organization_model().objects.filter(
                is_active=True,
                subscriptions__plan__organization=self.provider,
                subscriptions__ends_at__gt=ends_at),
            **filter_params
        ).select_related('user', 'organization')
        return queryset


class EngagedSubscribersAPIView(EngagedSubscribersSmartListMixin,
                               EngagedSubscribersQuerysetMixin,
                               ListAPIView):
    """
    Lists engaged subscribers

    Returns a list of {{PAGE_SIZE}} subscriber profiles which have or
    had a subscription to a plan provided by {organization}.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    **Tags**: subscriptions, provider, profilemodel

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/subscribers/engaged/?o=created_at&ot=desc\
 HTTP/1.1

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
                "email": "xia@localhost.localdomain",
                "created_at": "2016-01-14T23:16:55Z",
                "ends_at": "2017-01-14T23:16:55Z"
                }
            ]
        }
    """
    serializer_class = get_role_serializer()


class UnengagedSubscribersQuerysetMixin(DateRangeContextMixin,
                                       SubscribersQuerysetMixin):

    def get_queryset(self):
        ends_at = datetime_or_now(self.ends_at)
        kwargs = {'role__user__last_login__lt': ends_at}
        if self.start_at:
            kwargs.update({'role__user__last_login__gte': self.start_at})
        else:
            kwargs.update({
                'role__user__last_login__gte': ends_at - relativedelta(
                    days=settings.INACTIVITY_DAYS)})
        queryset = get_organization_model().objects.filter(
            is_active=True,
            subscribes_to__organization=self.provider,
            subscriptions__ends_at__gt=ends_at).exclude(**kwargs).distinct()
        return queryset


class UnengagedSubscribersAPIView(OrganizationSmartListMixin,
                                  UnengagedSubscribersQuerysetMixin,
                                  ListAPIView):
    """
    Lists inactive subscribers

    Returns a list of {{PAGE_SIZE}} subscriber profiles which have or
    had a subscription to a plan provided by {organization}.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    **Tags**: subscriptions, provider, profilemodel

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/subscribers/unengaged/?o=created_at&ot=desc\
 HTTP/1.1

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
                "email": "xia@localhost.localdomain",
                "created_at": "2016-01-14T23:16:55Z",
                "ends_at": "2017-01-14T23:16:55Z"
                }
            ]
        }
    """
    serializer_class = OrganizationDetailSerializer
