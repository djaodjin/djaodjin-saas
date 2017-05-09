# Copyright (c) 2017, DjaoDjin inc.
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

import logging

from django.core import validators
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.template.defaultfilters import slugify
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import (ListAPIView, CreateAPIView,
    ListCreateAPIView, DestroyAPIView, RetrieveUpdateDestroyAPIView)
from rest_framework.response import Response

from .. import settings
from ..mixins import (OrganizationMixin, RoleDescriptionMixin, RoleMixin,
    RoleSmartListMixin, UserMixin)
from ..models import Organization, RoleDescription
from ..utils import get_role_model
from .serializers import BaseRoleSerializer, RoleSerializer


LOGGER = logging.getLogger(__name__)


class OrganizationRoleCreateSerializer(serializers.Serializer):
    #pylint:disable=abstract-method

    slug = serializers.CharField(required=False, validators=[
        validators.RegexValidator(settings.ACCT_REGEX,
            _('Enter a valid organization slug.'), 'invalid')])
    email = serializers.EmailField(required=False)
    message = serializers.CharField(max_length=255, required=False)


class UserRoleCreateSerializer(serializers.Serializer):
    #pylint:disable=abstract-method

    slug = serializers.CharField(validators=[
        validators.RegexValidator(settings.ACCT_REGEX,
            _('Enter a valid username.'), 'invalid')])
    email = serializers.EmailField(required=False)
    message = serializers.CharField(max_length=255, required=False)


class RoleDescriptionCRUDRoleSerializer(BaseRoleSerializer):
    pass


class RoleDescriptionCRUDSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    slug = serializers.CharField(required=False)

    def get_roles(self, obj):
        roles_queryset = obj.role_set.filter(
            organization=self._context['view'].organization)
        return RoleDescriptionCRUDRoleSerializer(roles_queryset, many=True).data

    def create(self, validated_data):
        validated_data['organization'] = self._context['view'].organization
        return super(RoleDescriptionCRUDSerializer, self).create(validated_data)

    class Meta:
        model = RoleDescription
        fields = ('created_at', 'name', 'slug', 'is_global', 'roles')


class AccessibleByQuerysetMixin(UserMixin):

    def get_queryset(self):
        return get_role_model().objects.filter(user=self.user)


class AccessibleByListAPIView(RoleSmartListMixin,
                              AccessibleByQuerysetMixin, ListCreateAPIView):
    """
    ``GET`` lists all relations where an ``Organization`` is accessible by
    a ``User``. Typically the user was granted specific permissions through
    a ``Role``.

    ``POST`` Generates a request to attach a user to a role on an organization

    see :doc:`Flexible Security Framework <security>`.

    **Example request**:

    .. sourcecode:: http

        GET  /api/users/alice/accessibles/

    **Example response**:

    .. sourcecode:: http

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2012-10-01T09:00:00Z",
                    "organization": {
                        "slug": "cowork",
                        "full_name": "ABC Corp.",
                        "printable_name": "ABC Corp.",
                        "created_at": "2012-08-14T23:16:55Z",
                        "email": "support@localhost.localdomain"
                    },
                    "user": {
                        "slug": "alice",
                        "email": "alice@localhost.localdomain",
                        "full_name": "Alice Doe",
                        "created_at": "2012-09-14T23:16:55Z"
                    },
                    "name": "manager",
                    "request_key": null,
                    "grant_key": null
                }
            ]
        }

    **Example request**:

    .. sourcecode:: http

        POST /api/users/xia/accessibles/

        {
          "slug": "cowork"
        }

    **Example response**:

    .. sourcecode:: http

        {
          "slug": "cowork"
        }
    """
    serializer_class = RoleSerializer

    def create(self, request, *args, **kwargs): #pylint:disable=unused-argument
        serializer = OrganizationRoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = False
        reason = serializer.validated_data.get('message', None)
        if reason:
            reason = force_text(reason)

        slug = serializer.validated_data.get('slug', None)
        if slug:
            # XXX slugify because we actually pass a full_name when doesnt exist
            organizations = Organization.objects.filter(slug=slugify(slug))
        else:
            email = serializer.validated_data.get('email', None)
            if email:
                organizations = Organization.objects.filter(email=email)
        with transaction.atomic():
            if organizations.count() == 0:
                if not request.GET.get('force', False):
                    raise Http404("%s not found"
                        % serializer.validated_data['slug'])
                email = serializer.validated_data['email']
                full_name = serializer.validated_data.get('full_name', '')
                if not full_name:
                    full_name = serializer.validated_data['slug']
                organization = Organization.objects.create(
                    full_name=full_name, email=email)
                user_model = get_user_model()
                try:
                    manager = user_model.objects.get(email=email)
                except user_model.DoesNotExist:
                    manager = user_model.objects.create_user(email, email=email)
                organization.add_manager(manager, request_user=request.user)
                organizations = [organization]

            for organization in organizations:
                created |= organization.add_role_request(
                    self.user, reason=reason)

        if created:
            resp_status = status.HTTP_201_CREATED
        else:
            resp_status = status.HTTP_200_OK
        # We were going to return the list of managers here but
        # angularjs complains about deserialization of a list
        # while expecting a single object.
        return Response(serializer.validated_data, status=resp_status,
            headers=self.get_success_headers(serializer.validated_data))


class RoleDescriptionQuerysetMixin(OrganizationMixin):

    serializer_class = RoleDescriptionCRUDSerializer
    lookup_field = 'slug'
    lookup_url_kwarg = 'role'

    def get_queryset(self):
        return self.get_role_descriptions()

    @staticmethod
    def check_local(instance):
        if instance.is_global():
            raise PermissionDenied()


class RoleDescriptionListCreateView(RoleDescriptionQuerysetMixin,
                                    ListCreateAPIView):
    """
    List and create ``RoleDescription``.

    see :doc:`Flexible Security Framework <security>`.

    **Example request**:

    .. sourcecode:: http

        GET  /api/profile/cowork/roles/describe/

    **Example response**:

    .. sourcecode:: http

        {
            "count": 2,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2016-01-14T23:16:55Z",
                    "name": "Managers",
                    "slug": "manager",
                    "is_global": true,
                    "roles": [
                        {
                            "created_at": "2016-09-14T23:16:55Z",
                            "user": {
                                "slug": "donny",
                                "email": "support@djaodjin.com",
                                "full_name": "Donny Cooper",
                                "created_at": "2016-09-15T00:00:00Z"
                            },
                            "request_key": null,
                            "grant_key": null
                        },
                    ]
                },
                {
                    "created_at": "2012-09-14T23:16:55Z",
                    "name": "Contributors",
                    "slug": "contributor",
                    "is_global": true,
                    "roles": []
                }
            ]
        }
    """
    pass


class RoleDescriptionDetailView(RoleDescriptionQuerysetMixin,
                                RetrieveUpdateDestroyAPIView):
    """
    Create, retrieve, update and delete ``RoleDescription``.

    see :doc:`Flexible Security Framework <security>`.

    **Example request**:

    .. sourcecode:: http

        GET  /api/profile/cowork/roles/describe/manager

    **Example response**:

    .. sourcecode:: http

        {
            "created_at": "2016-01-14T23:16:55Z",
            "name": "Managers",
            "slug": "manager",
            "is_global": true,
            "roles": [
                {
                    "created_at": "2016-09-14T23:16:55Z",
                    "user": {
                        "slug": "donny",
                        "email": "support@djaodjin.com",
                        "full_name": "Donny Cooper",
                        "created_at": "2016-09-15T00:00:00Z"
                    },
                    "request_key": null,
                    "grant_key": null
                },
            ]
        }

    """
    def perform_update(self, serializer):
        self.check_local(serializer.instance)
        super(RoleDescriptionDetailView, self).perform_update(serializer)

    def perform_destroy(self, instance):
        self.check_local(instance)
        super(RoleDescriptionDetailView, self).perform_destroy(instance)


class RoleQuerysetMixin(OrganizationMixin):

    def get_queryset(self):
        return get_role_model().objects.filter(organization=self.organization)


class RoleListAPIView(RoleSmartListMixin, RoleQuerysetMixin, ListAPIView):
    """
    ``GET`` lists all roles for an organization

    **Example request**:

    .. sourcecode:: http

        GET /api/profile/cowork/roles/

    **Example response**:

    .. sourcecode:: http

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2012-10-01T09:00:00Z",
                    "role_description": {
                        "name": "Manager",
                        "slug": "manager",
                        "organization": {
                            "slug": "cowork",
                            "full_name": "ABC Corp.",
                            "printable_name": "ABC Corp.",
                            "created_at": "2012-08-14T23:16:55Z",
                            "email": "support@localhost.localdomain"
                        }
                    },
                    "user": {
                        "slug": "alice",
                        "email": "alice@localhost.localdomain",
                        "full_name": "Alice Doe",
                        "created_at": "2012-09-14T23:16:55Z"
                    },
                    "request_key": "1",
                    "grant_key": null
                },
            ]
        }
    """
    serializer_class = RoleSerializer


class RoleByDescrQuerysetMixin(RoleDescriptionMixin, RoleQuerysetMixin):

    def get_queryset(self):
        return super(RoleByDescrQuerysetMixin, self).get_queryset().filter(
            Q(role_description=self.role_description)
            | Q(request_key__isnull=False))


class RoleFilteredListAPIView(RoleSmartListMixin, RoleByDescrQuerysetMixin,
                              ListAPIView, CreateAPIView):
    """
    ``GET`` lists the specified role assignments for an organization.

    ``POST`` attaches a user to a role on an organization, typically granting
    permissions to the user with regards to managing an organization profile
    (see :doc:`Flexible Security Framework <security>`).

    **Example request**:

    .. sourcecode:: http

        GET /api/profile/cowork/roles/managers/

    **Example response**:

    .. sourcecode:: http

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2012-10-01T09:00:00Z",
                    "role_description": {
                        "name": "Manager",
                        "slug": "manager",
                        "organization": {
                            "slug": "cowork",
                            "full_name": "ABC Corp.",
                            "printable_name": "ABC Corp.",
                            "created_at": "2012-08-14T23:16:55Z",
                            "email": "support@localhost.localdomain"
                        }
                    },
                    "user": {
                        "slug": "alice",
                        "email": "alice@localhost.localdomain",
                        "full_name": "Alice Doe",
                        "created_at": "2012-09-14T23:16:55Z"
                    },
                    "request_key": "1",
                    "grant_key": null
                },
            ]
        }

    **Example request**:

    .. sourcecode:: http

        POST /api/profile/cowork/roles/managers/
        {
          "slug": "Xia"
        }

    **Example response**:

    .. sourcecode:: http

        {
          "slug": "Xia"
        }
    """
    serializer_class = RoleSerializer

    def create(self, request, *args, **kwargs): #pylint:disable=unused-argument
        grant_key = None
        serializer = UserRoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_model = get_user_model()
        try:
            user = user_model.objects.get(
                username=serializer.validated_data['slug'])
        except user_model.DoesNotExist:
            try:
                # The following SQL query is not folded into the previous
                # one so we can have a priority of username over email.
                user = user_model.objects.get(
                    email=serializer.validated_data['slug'])
            except user_model.DoesNotExist:
                if not request.GET.get('force', False):
                    raise Http404("%s not found"
                        % serializer.validated_data['slug'])
                full_name = serializer.validated_data.get('full_name', '')
                name_parts = full_name.split(' ')
                if len(name_parts) > 0:
                    first_name = name_parts[0]
                    last_name = ' '.join(name_parts[1:])
                else:
                    first_name = full_name
                    last_name = ''
                #pylint: disable=no-member
                user = user_model.objects.create_user(
                    serializer.validated_data['slug'],
                    email=serializer.validated_data['email'],
                    first_name=first_name, last_name=last_name)
                grant_key = self.organization.generate_role_key(user)

        reason = serializer.validated_data.get('message', None)
        if reason:
            reason = force_text(reason)
        created = self.organization.add_role(
            user, self.role_description, grant_key=grant_key, reason=reason,
            request_user=request.user)
        if created:
            resp_status = status.HTTP_201_CREATED
        else:
            resp_status = status.HTTP_200_OK
        # We were going to return the list of managers here but
        # angularjs complains about deserialization of a list
        # while expecting a single object.
        return Response(serializer.validated_data, status=resp_status,
            headers=self.get_success_headers(serializer.validated_data))


class RoleDetailAPIView(RoleMixin, DestroyAPIView):
    """
    Dettach a user from one or all roles with regards to an organization,
    typically resulting in revoking permissions from this user to manage
    part of an organization profile.
    """

    def destroy(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        roles = [str(role.role_description) for role in queryset]
        LOGGER.info("Remove roles %s for user '%s' on organization '%s'",
            roles, self.user, self.organization,
            extra={'event': 'remove-roles', 'user': self.user,
                'organization': self.organization.slug, 'roles': roles})
        queryset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
