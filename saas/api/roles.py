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

from django.core import validators
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.template.defaultfilters import slugify
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers, status
from rest_framework.generics import ListCreateAPIView, DestroyAPIView
from rest_framework.response import Response

from .. import settings
from ..compat import User
from ..mixins import (OrganizationMixin, RelationMixin,
    RoleSmartListMixin, UserMixin)
from ..models import Organization
from ..utils import get_role_model
from .serializers import RoleSerializer


class RoleCreateSerializer(serializers.Serializer):
    #pylint:disable=abstract-method

    slug = serializers.CharField(validators=[
        validators.RegexValidator(settings.ACCT_REGEX,
            _('Enter a valid username.'), 'invalid')])
    email = serializers.EmailField(required=False)
    message = serializers.CharField(max_length=255, required=False)


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
        serializer = RoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # XXX slugify because we actually pass a full_name when doesnt exist
            organization = Organization.objects.get(
                slug=slugify(serializer.validated_data['slug']))
        except Organization.DoesNotExist:
            if not request.GET.get('force', False):
                raise Http404("%s not found"
                    % serializer.validated_data['slug'])
            organization = None

        with transaction.atomic():
            if organization is None:
                email = serializer.validated_data['email']
                full_name = serializer.validated_data.get('full_name', '')
                if not full_name:
                    full_name = serializer.validated_data['slug']
                organization = Organization.objects.create(
                    full_name=full_name, email=email)
                try:
                    manager = User.objects.get(email=email)
                except User.DoesNotExist:
                    manager = User.objects.create_user(email, email=email)
                organization.add_manager(manager)

            reason = serializer.validated_data.get('message', None)
            if reason:
                reason = force_text(reason)
            created = organization.add_role_request(self.user, reason=reason)

        if created:
            resp_status = status.HTTP_201_CREATED
        else:
            resp_status = status.HTTP_200_OK
        # We were going to return the list of managers here but
        # angularjs complains about deserialization of a list
        # while expecting a single object.
        return Response(serializer.validated_data, status=resp_status,
            headers=self.get_success_headers(serializer.validated_data))


class RelationListAPIView(OrganizationMixin, ListCreateAPIView):

    queryset = User.objects.all()
    serializer_class = RoleSerializer

    def add_relation(self, user, reason=None):
        raise NotImplementedError(
            "add_relation should be overriden in derived classes.")

    def create(self, request, *args, **kwargs): #pylint:disable=unused-argument
        serializer = RoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = User.objects.get(
                username=serializer.validated_data['slug'])
        except User.DoesNotExist:
            try:
                # The following SQL query is not folded into the previous
                # one so we can have a priority of username over email.
                user = User.objects.get(
                    email=serializer.validated_data['slug'])
            except User.DoesNotExist:
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
                user = User.objects.create_user(
                    serializer.validated_data['slug'],
                    email=serializer.validated_data['email'],
                    first_name=first_name, last_name=last_name)

        reason = serializer.validated_data.get('message', None)
        if reason:
            reason = force_text(reason)
        if self.add_relation(user, reason=reason):
            resp_status = status.HTTP_201_CREATED
        else:
            resp_status = status.HTTP_200_OK
        # We were going to return the list of managers here but
        # angularjs complains about deserialization of a list
        # while expecting a single object.
        return Response(serializer.validated_data, status=resp_status,
            headers=self.get_success_headers(serializer.validated_data))


class RoleListAPIView(RelationListAPIView):
    """
    ``GET`` lists all relations with a specified role with regards
    to an organization.

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

    def add_relation(self, user, reason=None):
        role_name = self.kwargs.get('role')
        try:
            return self.organization.add_role(user, role_name, reason=reason)
        except ValueError:
            raise Http404("No role named '%s'" % role_name)

    def get_queryset(self):
        role_name = self.kwargs.get('role')
        if role_name.endswith('s'):
            role_name = role_name[:-1]
        return get_role_model().objects.filter(
            Q(name=role_name) | Q(request_key__isnull=False),
            organization=self.organization)


class RoleDetailAPIView(RelationMixin, DestroyAPIView):
    """
    Dettach a user from a role with regards to an organization, typically
    resulting in revoking permissions  from this user to manage part of an
    organization profile.
    """
    pass

