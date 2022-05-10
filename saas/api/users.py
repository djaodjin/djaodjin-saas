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

from django.http import Http404
from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, GenericAPIView
from rest_framework.exceptions import ValidationError

from .serializers import AgreementSignSerializer
from ..compat import gettext_lazy as _
from ..models import Agreement, Signature
from ..mixins import (ProviderMixin, UserSmartListMixin,
    DateRangeContextMixin)
from ..utils import get_role_model, get_user_serializer


#pylint: disable=no-init

class RegisteredQuerysetMixin(DateRangeContextMixin, ProviderMixin):
    """
    All ``User`` that have registered, and who are not associated
    to an ``Organization``, or whose ``Organization`` they are associated
    with has no ``Subscription``.
    """

    model = get_user_model()

    def get_queryset(self):
        # We would really like to generate this SQL but Django
        # and LEFT OUTER JOIN is a "complicated" relationship ...
        #   SELECT DISTINCT * FROM User LEFT OUTER JOIN (
        #     SELECT user_id FROM Role INNER JOIN Subscription
        #       ON Role.organization_id = Subscription.organization_id
        #       WHERE created_at < ends_at) AS RoleSubSet
        #     ON User.id = RoleSubSet.user_id
        #     WHERE user_id IS NULL;
        return self.model.objects.exclude(
            # OK to use filter because we want to see all users here.
            # XXX `self.ends_at` is coming from `UserSmartListMixin`
            pk__in=get_role_model().objects.filter(
            organization__subscriptions__created_at__lt=self.ends_at).values(
            'user')).order_by('-date_joined', 'last_name').distinct()


class RegisteredBaseAPIView(RegisteredQuerysetMixin, ListAPIView):

    pass


class RegisteredAPIView(UserSmartListMixin, RegisteredBaseAPIView):
    """
    Lists top of funnel registered users

    Returns a list of {{PAGE_SIZE}} users which have no associated role
    or a role to a profile which has no subscription, active or inactive.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    The API is typically used within an HTML
    `subscribers page </docs/themes/#dashboard_profile_subscribers>`_
    as present in the default theme.

    **Tags**: metrics, broker, usermodel

    **Examples**

    .. code-block:: http

        GET  /api/metrics/registered/ HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "slug": "alice",
                    "created_at": "2014-01-01T00:00:00Z",
                    "email": "alice@djaodjin.com",
                    "full_name": "Alice Cooper",
                    "printable_name": "Alice Cooper",
                    "username": "alice"
                }
            ]
        }
    """
    serializer_class = get_user_serializer()


class AgreementSignAPIView(GenericAPIView):
    """
    Signs a consent agreement

    Indicates the request user has signed the required consent agreement.

    The API is typically used within an HTML
    `legal agreement page </docs/themes/#workflow_legal_sign>`_
    as present in the default theme.

    **Tags**: profile, user, usermodel

    **Examples**

    .. code-block:: http

         POST /api/legal/terms-of-use/sign/ HTTP/1.1

    .. code-block:: json

        {
          "read_terms": true
        }

    responds

    .. code-block:: json

        {
          "read_terms": true,
          "last_signed": "2019-01-01T00:00:00Z"
        }
    """
    serializer_class = AgreementSignSerializer
    slug_url_kwarg = 'agreement'

    def post(self, request, *args, **kwargs): #pylint:disable=unused-argument
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data['read_terms']:
            slug = self.kwargs.get(self.slug_url_kwarg)
            try:
                record = Signature.objects.create_signature(
                    slug, self.request.user)
            except Agreement.DoesNotExist:
                raise Http404
            return Response(AgreementSignSerializer().to_representation({
                'read_terms': serializer.validated_data['read_terms'],
                'last_signed': record.last_signed}))
        raise ValidationError(_('You have to agree with the terms'))
