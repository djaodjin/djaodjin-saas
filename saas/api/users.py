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

from rest_framework.generics import ListAPIView

from .serializers import UserSerializer
from ..compat import User
from ..mixins import ProviderMixin, UserSmartListMixin
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
        self.cache_fields(self.request)
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
                    "slug": "alice",
                    "email": "alice@djaodjin.com",
                    "full_name": "Alice Cooper",
                    "created_at": "2014-01-01T00:00:00Z"
                }
            ]
        }
    """
    serializer_class = UserSerializer


class UserQuerysetMixin(object):
    """
    All ``User``.
    """

    @staticmethod
    def get_queryset():
        return User.objects.all()


class UserListAPIView(UserSmartListMixin, UserQuerysetMixin, ListAPIView):
    """
    GET queries all ``User``.

    .. autoclass:: saas.mixins.UserSmartListMixin

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
                    "slug": "alice",
                    "email": "alice@djaodjin.com",
                    "full_name": "Alice Cooper",
                    "created_at": "2014-01-01T00:00:00Z"
                }
            ]
        }
    """
    serializer_class = UserSerializer
