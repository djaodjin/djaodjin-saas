# Copyright (c) 2025, DjaoDjin inc.
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
from __future__ import unicode_literals

from rest_framework import generics, status, response as http

from .serializers import AtTimeSerializer
from ..docs import extend_schema
from ..mixins import OrganizationMixin
from ..utils import datetime_or_now
from ..renewals import (create_charge_for_balance_organization,
    complete_charges, extend_subscriptions_organization)


class RenewalsAPIView(OrganizationMixin, generics.CreateAPIView):

    serializer_class = AtTimeSerializer
    schema = None

    @extend_schema(responses={
      200: None})
    def post(self, request, *args, **kwargs):
        """
        Trigger renewals for an organization

        Trigger renewals for an organization

        **Tags**: billing, broker

        **Examples**

        .. code-block:: http

            POST /api/billing/xia/renew HTTP/1.1

        .. code-block:: json


            {
                "at_time": "2024-11-10"
            }

        responds

        .. code-block:: json

           {
           }
        """
        return self.create(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):#pylint:disable=unused-argument
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        at_time = datetime_or_now(serializer.validated_data.get('at_time'))
        extend_subscriptions_organization(self.organization, at_time=at_time)
        nb_charges = create_charge_for_balance_organization(
            self.organization, until=at_time)
        # We will wait until the charge settles, and create
        # the `payment_successful` transactions.
        complete_charges()
        return http.Response({}, status=(
            status.HTTP_201_CREATED if nb_charges > 0 else status.HTTP_200_OK))
