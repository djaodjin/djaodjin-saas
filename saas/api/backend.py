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

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import (RetrieveAPIView,
    RetrieveUpdateDestroyAPIView)
from rest_framework.response import Response

from ..backends import ProcessorError
from ..docs import swagger_auto_schema, OpenAPIResponse
from ..mixins import OrganizationMixin
from .serializers import (BankSerializer, CardSerializer,
    CardTokenSerializer)

#pylint: disable=no-init
#pylint: disable=old-style-class

class RetrieveBankAPIView(OrganizationMixin, RetrieveAPIView):
    """
    Pass through that calls the processor API to retrieve some details about
    the deposit account associated to a provider (if that information is
    available through the :doc:`payment processor backend<backends>` API).

    This API does not trigger payment of a subscriber to a provider. Checkout
    of a subscription cart is done either through the
    :ref:`HTML page<pages_cart>` or :ref:`API end point<api_checkout>`.

    **Examples

    .. code-block:: http

        GET /api/billing/cowork/bank/ HTTP/1.1

    responds

    .. code-block:: json

        {
          "bank_name": "Stripe Test Bank",
          "last4": "***-htrTZ",
          "balance_amount": 0,
          "balance_unit": "usd"
        }
    """
    serializer_class = BankSerializer

    def retrieve(self, request, *args, **kwargs):
        #pylint: disable=unused-argument
        return Response(
            self.organization.retrieve_bank())


class RetrieveCardAPIView(OrganizationMixin, RetrieveUpdateDestroyAPIView):
    """
    Pass through to the processor to retrieve some details about
    the payment method (ex: credit card) associated to a subscriber.

    **Examples

    .. code-block:: http

        GET /api/billing/cowork/card/ HTTP/1.1

    responds

    .. code-block:: json

        {
          "last4": "1234",
          "exp_date": "12/2019"
        }
    """
    serializer_class = CardSerializer

    def delete(self, request, *args, **kwargs):
        """
        Pass through to the processor to remove the payment method (ex: credit
        card) associated to a subscriber.

        **Examples

        .. code-block:: http

            DELETE /api/billing/cowork/card/ HTTP/1.1
        """
        return super(RetrieveCardAPIView, self).delete(request, *args, **kwargs)

    @swagger_auto_schema(request_boby=CardTokenSerializer, responses={
        200: OpenAPIResponse("", CardSerializer)})
    def put(self, request, *args, **kwargs):
        """
        Pass through to the processor to update some details about
        the payment method (ex: credit card) associated to a subscriber.

        **Examples

        .. code-block:: http

            PUT /api/billing/cowork/card/ HTTP/1.1

        .. code-block:: json

            {
              "token": "xyz",
            }

        responds

        .. code-block:: json

            {
              "last4": "1234",
              "exp_date": "12/2019"
            }
        """
        return super(RetrieveCardAPIView, self).put(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self.organization.delete_card()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def retrieve(self, request, *args, **kwargs):
        #pylint: disable=unused-argument
        return Response(self.organization.retrieve_card())

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        serializer = CardTokenSerializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']
        try:
            self.organization.update_card(token, self.request.user)
        except ProcessorError as err:
            raise ValidationError(err)
        return self.retrieve(request, *args, **kwargs)
