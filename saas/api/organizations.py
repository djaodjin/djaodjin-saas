# Copyright (c) 2020, DjaoDjin inc.
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

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model, logout as auth_logout
from django.db import transaction, IntegrityError
from django.utils.encoding import force_text
from rest_framework import parsers, status
from rest_framework.generics import (CreateAPIView, ListAPIView,
    ListCreateAPIView, RetrieveUpdateDestroyAPIView)
from rest_framework.response import Response

from .serializers import (OrganizationCreateSerializer,
    OrganizationDetailSerializer, OrganizationWithSubscriptionsSerializer,
    UploadBlobSerializer)
from .. import settings, signals
from ..decorators import _valid_manager
from ..docs import swagger_auto_schema
from ..mixins import (OrganizationMixin, OrganizationSmartListMixin,
    ProviderMixin, OrganizationDecorateMixin)
from ..models import get_broker
from ..utils import (full_name_natural_split, get_organization_model,
    get_role_model, handle_uniq_error, get_picture_storage)


#pylint: disable=no-init
class OrganizationCreateMixin(object):

    user_model = get_user_model()

    def create_organization(self, validated_data):
        organization_model = get_organization_model()
        organization = organization_model(
            slug=validated_data.get('slug', None),
            full_name=validated_data.get('full_name'),
            email=validated_data.get('email'),
            default_timezone=validated_data.get(
                'default_timezone', settings.TIME_ZONE),
            phone=validated_data.get('phone', ""),
            street_address=validated_data.get('street_address', ""),
            locality=validated_data.get('locality', ""),
            region=validated_data.get('region', ""),
            postal_code=validated_data.get('postal_code', ""),
            country=validated_data.get('country', ""),
            extra=validated_data.get('extra'))
        organization.is_personal = (validated_data.get('type') == 'personal')
        with transaction.atomic():
            try:
                if organization.is_personal:
                    try:
                        user = self.user_model.objects.get(
                            username=organization.slug)
                        if not organization.full_name:
                            organization.full_name = user.get_full_name()
                        if not organization.email:
                            organization.email = user.email
                        # We are saving the `Organization` after the `User`
                        # exists in the database so we can retrieve
                        # the full_name and email from that attached user
                        # if case they were not provided in the API call.
                        organization.save()
                    except self.user_model.DoesNotExist:
                        #pylint:disable=unused-variable
                        # We are saving the `Organization` when the `User`
                        # does not exist so we have a chance to create
                        # a slug/username.
                        organization.save()
                        first_name, mid, last_name = full_name_natural_split(
                            organization.full_name)
                        user = self.user_model.objects.create_user(
                            username=organization.slug,
                            email=organization.email,
                            first_name=first_name,
                            last_name=last_name)
                    organization.add_manager(
                        user, request_user=self.request.user)
                else:
                    # When `slug` is not present, `save` would try to create
                    # one from the `full_name`.
                    organization.save()
            except IntegrityError as err:
                handle_uniq_error(err)

        return organization


class OrganizationQuerysetMixin(OrganizationDecorateMixin):

    queryset = get_organization_model().objects.all()


class OrganizationDetailAPIView(OrganizationMixin, OrganizationQuerysetMixin,
                                RetrieveUpdateDestroyAPIView):
    """
    Retrieves a billing profile

    **Tags**: profile

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
    lookup_url_kwarg = 'organization'
    serializer_class = OrganizationWithSubscriptionsSerializer
    user_model = get_user_model()

    def put(self, request, *args, **kwargs):
        """
        Updates a billing profile

        **Tags**: profile

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

        We anonymize the organization instead of purely deleting
        it from the database because we don't want to loose history
        on subscriptions and transactions.

        **Tags**: profile

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
    """
    parser_classes = (parsers.FormParser, parsers.MultiPartParser)
    serializer_class = UploadBlobSerializer

    def post(self, request, *args, **kwargs):
        #pylint:disable=unused-argument
        uploaded_file = request.data.get('file')
        if not uploaded_file:
            return Response({'details': "no location or file specified."},
                status=status.HTTP_400_BAD_REQUEST)

        # tentatively extract file extension.
        parts = os.path.splitext(
            force_text(uploaded_file.name.replace('\\', '/')))
        ext = parts[-1].lower() if len(parts) > 1 else ""
        key_name = "%s%s" % (
            hashlib.sha256(uploaded_file.read()).hexdigest(), ext)
        default_storage = get_picture_storage()
        location = self.request.build_absolute_uri(default_storage.url(
            default_storage.save(key_name, uploaded_file)))
        self.organization.picture = location
        self.organization.save()
        return Response({'location': location}, status=status.HTTP_201_CREATED)


class OrganizationListAPIView(OrganizationSmartListMixin,
                              OrganizationQuerysetMixin,
                              OrganizationCreateMixin, ListCreateAPIView):
    """
    List billing profiles

    Queries a page (``PAGE_SIZE`` records) of organization and user profiles.

    The queryset can be filtered for at least one field to match a search
    term (``q``).

    The queryset can be ordered by a field by adding an HTTP query parameter
    ``o=`` followed by the field name. A sequence of fields can be used
    to create a complete ordering by adding a sequence of ``o`` HTTP query
    parameters. To reverse the natural order of a field, prefix the field
    name by a minus (-) sign.

    **Tags**: profile

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

    @swagger_auto_schema(request_body=OrganizationCreateSerializer)
    def post(self, request, *args, **kwargs):
        """
        Creates an organization, personal or user profile.

        **Examples**

        .. code-block:: http

            POST /api/profile/ HTTP/1.1

        .. code-block:: json

            {
              "email": "xia@locahost.localdomain",
              "full_name": "Xia Lee",
              "type": "personal"
            }
        """
        return self.create(request, *args, **kwargs)

    def paginate_queryset(self, queryset):
        page = super(OrganizationListAPIView, self).paginate_queryset(queryset)
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
        serializer = self.get_serializer(instance=organization)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data,
            status=status.HTTP_201_CREATED, headers=headers)


class SubscribersQuerysetMixin(OrganizationDecorateMixin, ProviderMixin):

    def get_queryset(self):
        queryset = get_organization_model().objects.filter(
            subscriptions__organization=self.provider)
        return queryset

    def paginate_queryset(self, queryset):
        page = super(SubscribersQuerysetMixin, self).paginate_queryset(queryset)
        page = self.decorate_personal(page)
        return page


class SubscribersAPIView(OrganizationSmartListMixin,
                         SubscribersQuerysetMixin, ListAPIView):
    """
    Lists subscribers for a provider

    Returns a PAGE_SIZE list of subscriber profiles which have or had
    a subscription to a plan provided by {organization}.

    **Tags**: subscriptions

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
