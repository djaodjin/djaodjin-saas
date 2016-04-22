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

from django.http import Http404
from django.utils.encoding import force_text
from rest_framework import status
from rest_framework.generics import (DestroyAPIView, ListAPIView,
    ListCreateAPIView)
from rest_framework.response import Response

from .serializers import UserSerializer
from ..compat import User
from ..mixins import (OrganizationMixin, ProviderMixin, RelationMixin,
    UserSmartListMixin)
from ..utils import get_role_model


#pylint: disable=no-init
#pylint: disable=old-style-class

class RegisteredQuerysetMixin(ProviderMixin):
    """
    All ``User`` that have registered, and who are not associated
    to an ``Organization``, or whose ``Organization`` they are associated
    with has no ``Subscription``.
    """

    model = User

    def get_queryset(self):
        # We would really like to generate this SQL but Django
        # and LEFT OUTER JOIN is a "complicated" relationship ...
        #   SELECT DISTINCT * FROM User LEFT OUTER JOIN (
        #     SELECT user_id FROM Role INNER JOIN Subscription
        #       ON Role.organization_id = Subscription.organization_id
        #       WHERE created_at < ends_at) AS RoleSubSet
        #     ON User.id = RoleSubSet.user_id
        #     WHERE user_id IS NULL;
        return User.objects.exclude(pk__in=get_role_model().objects.filter(
            organization__subscription__created_at__lt=self.ends_at).values(
            'user')).order_by('-date_joined', 'last_name').distinct()


class RegisteredBaseAPIView(RegisteredQuerysetMixin, ListAPIView):

    pass


class RegisteredAPIView(UserSmartListMixin, RegisteredBaseAPIView):
    """
    GET queries all ``User`` which have no associated role or a role
    to an ``Organization`` which has no Subscription, active or inactive.

    The queryset can be further filtered to a range of dates between
    ``start_at`` and ``ends_at``.

    The queryset can be further filtered by passing a ``q`` parameter.
    The value in ``q`` will be matched against:

      - User.first_name
      - User.last_name
      - User.email

    The result queryset can be ordered by:

      - User.first_name
      - User.last_name
      - User.email
      - User.created_at

    **Example request**:

    .. sourcecode:: http

        GET /api/metrics/registered?o=created_at&ot=desc

    **Example response**:

    .. sourcecode:: http

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "username": "alice",
                    "email": "alice@djaodjin.com",
                    "full_name": "Alice Cooper",
                    "created_at": "2014-01-01T00:00:00Z"
                }
            ]
        }
    """
    serializer_class = UserSerializer


class RelationListAPIView(OrganizationMixin, ListCreateAPIView):

    queryset = User.objects.all()
    serializer_class = UserSerializer

    def add_relation(self, user, reason=None):
        raise NotImplementedError(
            "add_relation should be overriden in derived classes.")

    def create(self, request, *args, **kwargs): #pylint:disable=unused-argument
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = User.objects.get(
                username=serializer.validated_data['username'])
        except User.DoesNotExist:
            try:
                # The following SQL query is not folded into the previous
                # one so we can have a priority of username over email.
                user = User.objects.get(
                    email=serializer.validated_data['username'])
            except User.DoesNotExist:
                if not request.GET.get('force', False):
                    raise Http404("%s not found"
                        % serializer.validated_data['username'])
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
                    serializer.validated_data['username'],
                    email=serializer.validated_data['email'],
                    first_name=first_name, last_name=last_name)

        reason = request.data.get('invite', None)
        if reason:
            reason = force_text(reason)
        if self.add_relation(user,
                reason=reason):
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
    ``GET`` lists all users with a specified role with regards
    to an organization.

    ``POST`` attaches a user to a role on an organization, typically granting
    permissions to the user with regards to managing an organization profile
    (see :doc:`Flexible Security Framework <security>`).

    **Example request**:

    .. sourcecode:: http

        GET /api/profile/cowork/roles/managers/

    **Example response**:

    .. sourcecode:: http

        [
            {
                "username": "alice",
                "email": "alice@djaodjin.com",
                "full_name": "Alice Cooper",
                "created_at": "2014-01-01T00:00:00Z"
            },
            {
                "username": "xia",
                "email": "xia@djaodjin.com",
                "full_name": "Xia Lee",
                "created_at": "2014-01-01T00:00:00Z"
            }
        ]
    """

    def add_relation(self, user, reason=None):
        role_name = self.kwargs.get('role')
        try:
            return self.organization.add_role(user, role_name, reason=reason)
        except ValueError:
            raise Http404("No role named '%s'" % role_name)

    def get_queryset(self):
        return self.organization.with_role(self.kwargs.get('role'))


class RoleDetailAPIView(RelationMixin, DestroyAPIView):
    """
    Dettach a user from a role with regards to an organization, typically
    resulting in revoking permissions  from this user to manage part of an
    organization profile.
    """
    pass


class UserQuerysetMixin(object):
    """
    All ``User``.
    """
    model = User

    def get_queryset(self):
        return User.objects.filter(date_joined__lt=self.ends_at)


class UserListAPIView(UserSmartListMixin, UserQuerysetMixin, ListAPIView):
    """
    GET queries all ``User``.

    The queryset can be further filtered to a range of dates between
    ``start_at`` and ``ends_at``.

    The queryset can be further filtered by passing a ``q`` parameter.
    The value in ``q`` will be matched against:

      - User.first_name
      - User.last_name
      - User.email

    The result queryset can be ordered by:

      - User.first_name
      - User.last_name
      - User.email
      - User.created_at

    **Example request**:

    .. sourcecode:: http

        GET /api/users/?o=created_at&ot=desc

    **Example response**:

    .. sourcecode:: http

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "username": "alice",
                    "email": "alice@djaodjin.com",
                    "full_name": "Alice Cooper",
                    "created_at": "2014-01-01T00:00:00Z"
                }
            ]
        }
    """
    serializer_class = UserSerializer
