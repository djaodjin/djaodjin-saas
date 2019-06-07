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

from django.http import Http404
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, GenericAPIView
from rest_framework.exceptions import ValidationError

from .serializers import UserSerializer, AgreementSignSerializer
from ..models import Agreement, Signature
from ..mixins import (ProviderMixin, UserSmartListMixin,
    DateRangeContextMixin)
from ..utils import get_role_model


#pylint: disable=no-init
#pylint: disable=old-style-class

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
            organization__subscription__created_at__lt=self.ends_at).values(
            'user')).order_by('-date_joined', 'last_name').distinct()


class RegisteredBaseAPIView(RegisteredQuerysetMixin, ListAPIView):

    pass


class RegisteredAPIView(UserSmartListMixin, RegisteredBaseAPIView):
    """
    Lists all ``User`` which have no associated role or a role
    to an ``Organization`` which has no Subscription, active or inactive.

    The queryset can be filtered to a range of dates
    ([``start_at``, ``ends_at``]) and for at least one field to match a search
    term (``q``).

    Query results can be ordered by natural fields (``o``) in either ascending
    or descending order (``ot``).

    **Tags: metrics

    **Examples

    .. code-block:: http

        GET  /api/metrics/registered?o=created_at&ot=desc HTTP/1.1

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


class AgreementSignAPIView(GenericAPIView):
    serializer_class = AgreementSignSerializer
    slug_url_kwarg = 'agreement'

    def post(self, request, *args, **kwargs):
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
        else:
            raise ValidationError(_('You have to agree with the terms'))
