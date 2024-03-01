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

import hashlib, logging, os, re

from dateutil.relativedelta import relativedelta
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model, logout as auth_logout
from django.db import transaction, IntegrityError
from rest_framework import parsers, status
from rest_framework.generics import (CreateAPIView, ListAPIView,
    RetrieveUpdateDestroyAPIView)
from rest_framework.response import Response

from .serializers import (EngagedSubscriberSerializer, OrganizationSerializer,
    OrganizationDetailSerializer, OrganizationWithSubscriptionsSerializer,
    UploadBlobSerializer)
from .. import settings, signals
from ..compat import force_str, gettext_lazy as _, urlparse, urlunparse
from ..decorators import _valid_manager
from ..filters import OrderingFilter, SearchFilter
from ..mixins import (DateRangeContextMixin, OrganizationMixin,
    OrganizationSearchOrderListMixin, OrganizationSmartListMixin,
    ProviderMixin, OrganizationDecorateMixin)
from ..models import get_broker, Subscription
from ..utils import (build_absolute_uri, datetime_or_now,
    get_organization_model, get_role_model, get_picture_storage,
    handle_uniq_error)


LOGGER = logging.getLogger(__name__)


class OrganizationQuerysetMixin(OrganizationDecorateMixin):

    queryset = get_organization_model().objects.all()


class OrganizationDetailAPIView(OrganizationMixin, OrganizationQuerysetMixin,
                                RetrieveUpdateDestroyAPIView):
    """
    Retrieves a profile

    The API is typically used within an HTML
    `contact information page </docs/guides/themes/#dashboard_profile>`_
    as present in the default theme.

    **Tags**: profile, subscriber, profilemodel

    **Examples**

    .. code-block:: http

        GET /api/profile/xia HTTP/1.1

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
            "type": "personal",
            "picture": "",
            "subscriptions": [
                {
                    "created_at": "2018-01-01T00:00:00Z",
                    "ends_at": "2019-01-01T00:00:00Z",
                    "plan": {
                        "slug": "open-space",
                        "title": "Open Space"
                    },
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
        Updates a profile

        The API is typically used within an HTML
        `contact information page </docs/guides/themes/#dashboard_profile>`_
        as present in the default theme.

        **Tags**: profile, subscriber, profilemodel

        **Examples**

        .. code-block:: http

            PUT /api/profile/xia HTTP/1.1

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
        Deletes a profile

        We anonymize the profile instead of purely deleting
        it from the database because we don't want to loose history
        on subscriptions and transactions.

        The API is typically used within an HTML
        `contact information page </docs/guides/themes/#dashboard_profile>`_
        as present in the default theme.

        **Tags**: profile, subscriber, profilemodel

        **Examples**

        .. code-block:: http

            DELETE /api/profile/xia HTTP/1.1
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
            signals.profile_updated.send(sender=__name__,
                organization=serializer.instance, changes=changes,
                user=self.request.user)
        except IntegrityError as err:
            handle_uniq_error(err)

    def destroy(self, request, *args, **kwargs): #pylint:disable=unused-argument
        """
        Archive the organization. We don't to loose the subscriptions
        and transactions history.
        """
        at_time = datetime_or_now()
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
            Subscription.objects.filter(
                organization=obj, ends_at__gt=at_time).update(ends_at=at_time)
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

            POST /api/profile/xia/picture HTTP/1.1

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

        LOGGER.debug("upload picture to %s on storage %s",
            key_name, default_storage)
        location = default_storage.url(
            default_storage.save(key_name, uploaded_file))
        # We are removing the query parameters, as they contain
        # signature information, not the relevant URL location.
        parts = urlparse(location)
        location = urlunparse((parts.scheme, parts.netloc, parts.path,
            "", "", ""))
        location = build_absolute_uri(self.request, location=location)

        self.organization.picture = location
        self.organization.save()
        return Response({'location': location}, status=status.HTTP_201_CREATED)


class OrganizationListAPIView(OrganizationSmartListMixin,
                              OrganizationQuerysetMixin,
                              ListAPIView):
    """
    Lists profiles

    Returns a list of {{PAGE_SIZE}} profile and user accounts.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    **Tags**: profile, list, broker, profilemodel

    **Examples**

    .. code-block:: http

        GET /api/profile?o=created_at HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "slug": "xia",
                    "created_at": "2018-01-01T00:00:00Z",
                    "email": "xia@locahost.localdomain",
                    "full_name": "Xia Lee",
                    "printable_name": "Xia Lee",
                    "phone": "555-555-5555",
                    "street_address": "185 Berry St #550",
                    "locality": "San Francisco",
                    "region": "CA",
                    "postal_code": "",
                    "country": "US",
                    "default_timezone": "Los Angeles",
                    "is_provider": false,
                    "is_bulk_buyer": false,
                    "type": "personal",
                    "picture": ""
                }
            ]
        }
    """
    serializer_class = OrganizationDetailSerializer
    user_model = get_user_model()

    def paginate_queryset(self, queryset):
        page = super(OrganizationListAPIView, self).paginate_queryset(queryset)
        page = self.decorate_personal(page)
        return page


class ProviderAccessiblesQuerysetMixin(OrganizationDecorateMixin,
                                       ProviderMixin):

    def get_queryset(self):
        queryset = get_organization_model().objects.filter(is_active=True,
            subscribes_to__organization=self.provider).distinct()
        return queryset

    def paginate_queryset(self, queryset):
        page = super(ProviderAccessiblesQuerysetMixin, self).paginate_queryset(
            queryset)
        page = self.decorate_personal(page)
        return page


class ProviderAccessiblesAPIView(OrganizationSmartListMixin,
                                 ProviderAccessiblesQuerysetMixin, ListAPIView):
    """
    Lists subscribers

    Returns a list of {{PAGE_SIZE}} subscribers which have or
    had a subscription to a plan of the specified provider {profile}.

    The queryset can be filtered for at least one field to match a search
    term (``q``) and/or intersects a period (``start_at``, ``ends_at``).

    Returned results can be ordered by natural fields (``o``) in either
    ascending or descending order by using the minus sign ('-') in front
    of the ordering field name.

    The API is typically used in search forms linked to providers.

    **Tags**: list, provider, profilemodel, subscriptions

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/subscribers/all?o=created_at&ot=desc HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "slug": "xia",
                    "printable_name": "Xia Lee",
                    "picture": null,
                    "type": "personal",
                    "credentials": true
                }
            ]
        }
    """
    serializer_class = OrganizationSerializer


class ActiveSubscribersQuerysetMixin(DateRangeContextMixin,
                                     OrganizationDecorateMixin, ProviderMixin):

    def get_queryset(self):
        ends_at = datetime_or_now(self.ends_at)
        queryset = get_organization_model().objects.filter(is_active=True,
            subscribes_to__organization=self.provider,
            subscriptions__ends_at__gt=ends_at).distinct()
        return queryset

    def paginate_queryset(self, queryset):
        page = super(ActiveSubscribersQuerysetMixin, self).paginate_queryset(
            queryset)
        page = self.decorate_personal(page)
        return page


class ActiveSubscribersAPIView(OrganizationSmartListMixin,
                               ActiveSubscribersQuerysetMixin, ListAPIView):
    """
    Lists active subscribers

    Returns a list of {{PAGE_SIZE}} subscribers which have an active
    subscription to a plan of the specified provider {profile}.

    The queryset can be filtered for at least one field to match a search
    term (``q``) and/or intersects a period (``start_at``, ``ends_at``).

    Returned results can be ordered by natural fields (``o``) in either
    ascending or descending order by using the minus sign ('-') in front
    of the ordering field name.

    The API is typically used in search forms linked to providers.

    **Tags**: list, provider, profilemodel, subscriptions

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/subscribers?o=created_at&ot=desc HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "slug": "xia",
                    "printable_name": "Xia Lee",
                    "picture": null,
                    "type": "personal",
                    "credentials": true
                }
            ]
        }
    """
    serializer_class = OrganizationSerializer


class EngagedSubscribersSmartListMixin(object):
    """
    reporting entities list which is also searchable and sortable.
    """
    search_fields = (
        'first_name',
        'last_name',
        'profile',
        'profile__full_name'
    )
    alternate_fields = {
        'profile': 'organization__slug',
        'profile__full_name': 'organization__full_name'
    }
    ordering_fields = (
        ('user__last_login', 'created_at'),
        ('user__first_name', 'first_name'),
        ('user__last_name', 'last_name'),
        ('organization__slug', 'profile'),
        ('organization__full_name', 'profile__full_name')
    )

    ordering = ('created_at',)

    filter_backends = (SearchFilter, OrderingFilter,) # No `DateRangeFilter`
         # because the date range filter is applied as part
         # of `EngagedSubscribersQuerysetMixin`.


class EngagedSubscribersQuerysetMixin(ActiveSubscribersQuerysetMixin):

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
            organization__in=super(
                EngagedSubscribersQuerysetMixin, self).get_queryset(),
            **filter_params
        ).select_related('user', 'organization')
        return queryset


class EngagedSubscribersAPIView(EngagedSubscribersSmartListMixin,
                               EngagedSubscribersQuerysetMixin,
                               ListAPIView):
    """
    Lists engaged subscribers

    Returns a list of {{PAGE_SIZE}} subscribers which have or
    had a subscription to a plan of the specified provider {profile}.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    **Tags**: list, provider, rolemodel, subscriptions

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/subscribers/engaged?o=created_at&ot=desc\
 HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                  "created_at": "2022-01-01T00:00:00Z",
                  "user": {
                    "slug": "xia23",
                    "email": "123@example.com",
                    "full_name": "",
                    "created_at": "2022-01-01T00:00:00Z",
                    "last_login": "2022-01-01T00:00:00Z"
                  },
                  "role_description": {
                    "created_at": "2022-01-01T00:00:00Z",
                    "slug": "manager",
                    "title": "Profile Manager",
                    "skip_optin_on_grant": false,
                    "implicit_create_on_none": false,
                    "is_global": true,
                    "profile": null,
                    "extra": null
                  },
                  "accept_request_api_url": "http://127.0.0.1:8000/api/profile/xia23/roles/manager",
                  "remove_api_url": "http://127.0.0.1:8000/api/profile/xia23/roles/manager/admin",
                  "profile": {
                    "slug": "xia23",
                    "printable_name": "Xia23",
                    "picture": null,
                    "type": "organization",
                    "credentials": false,
                    "created_at": "2022-01-01T00:00:00Z"
                  }
                }
            ]
        }
    """
    serializer_class = EngagedSubscriberSerializer


class UnengagedSubscribersQuerysetMixin(ActiveSubscribersQuerysetMixin):

    def get_queryset(self):
        ends_at = datetime_or_now(self.ends_at)
        kwargs = {'role__user__last_login__lt': ends_at}
        if self.start_at:
            kwargs.update({'role__user__last_login__gte': self.start_at})
        else:
            kwargs.update({
                'role__user__last_login__gte': ends_at - relativedelta(
                    days=settings.INACTIVITY_DAYS)})
        one_login_within_period = get_organization_model().objects.filter(
            **kwargs)
        queryset = super(
            UnengagedSubscribersQuerysetMixin, self).get_queryset().exclude(
            pk__in=one_login_within_period).distinct()
        return queryset


class UnengagedSubscribersAPIView(OrganizationSearchOrderListMixin,
                                  UnengagedSubscribersQuerysetMixin,
                                  ListAPIView):
    """
    Lists inactive subscribers

    Returns a list of {{PAGE_SIZE}} subscribers which have or
    had a subscription to a plan of the specified provider {profile}.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    **Tags**: list, provider, profilemodel, subscriptions

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/subscribers/unengaged?o=created_at&ot=desc\
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
                "printable_name": "Xia Lee",
                "picture": null,
                "type": "organization",
                "credentials": false,
                "created_at": "2016-01-14T23:16:55Z"
                }
            ]
        }
    """
    serializer_class = OrganizationSerializer
