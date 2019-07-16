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
from __future__ import unicode_literals

from django.http import Http404
from django.db import transaction
from django.utils.translation import ugettext_lazy as _
from rest_framework import status
from rest_framework.generics import (CreateAPIView, ListAPIView,
    GenericAPIView, RetrieveAPIView)
from rest_framework.response import Response

from .serializers import (ChargeSerializer, EmailChargeReceiptSerializer,
    RefundChargeSerializer, ValidationErrorSerializer)
from .. import signals
from ..docs import OpenAPIResponse, swagger_auto_schema
from ..filters import DateRangeFilter, OrderingFilter, SearchFilter
from ..models import Charge, InsufficientFunds
from ..mixins import ChargeMixin, OrganizationMixin
from ..pagination import TotalPagination

#pylint: disable=no-init
#pylint: disable=old-style-class

class RetrieveChargeMixin(ChargeMixin):
    """
    Mixin for a ``Charge`` object that will first retrieve the state of
    the ``Charge`` from the processor API.

    This mixin is intended to be used for API requests. Pages should
    use the parent ChargeMixin and use AJAX calls to retrieve the state
    of a ``Charge`` in order to deal with latency and service errors
    from the processor.
    """
    model = Charge
    slug_field = 'processor_key'
    slug_url_kwarg = 'charge'

    def get_object(self, queryset=None):
        charge = super(RetrieveChargeMixin, self).get_object(queryset)
        charge.retrieve()
        return charge


class ChargeResourceView(RetrieveChargeMixin, RetrieveAPIView):
    """
    Retrieves a single processor charge

    Pass through to the processor and returns details about a ``Charge``.

    **Tags: billing

    **Examples

    .. code-block:: http

        GET /api/billing/charges/ch_XAb124EF/ HTTP/1.1

    responds

    .. code-block:: json

        {
            "created_at": "2016-01-01T00:00:01Z",
            "readable_amount": "$1121.20",
            "amount": 112120,
            "unit": "usd",
            "description": "Charge for subscription to cowork open-space",
            "last4": "1234",
            "exp_date": "12/2016",
            "processor_key": "ch_XAb124EF",
            "state": "DONE"
        }
    """
    serializer_class = ChargeSerializer


class SmartChargeListMixin(object):
    """
    Subscriber list which is also searchable and sortable.
    """
    search_fields = ('description',
                     'processor_key',
                     'customer__full_name')

    ordering_fields = [('description', 'description'),
                           ('amount', 'amount'),
                           ('customer__full_name', 'Full name'),
                           ('created_at', 'created_at')]

    filter_backends = (DateRangeFilter, OrderingFilter, SearchFilter)


class ChargeQuerysetMixin(object):

    @staticmethod
    def get_queryset():
        return Charge.objects.all()


class ChargeListAPIView(SmartChargeListMixin,
                        ChargeQuerysetMixin, ListAPIView):
    """
    Lists processor charges

    Queries a page (``PAGE_SIZE`` records) of ``Charge`` that were created
    on the processor.

    The queryset can be filtered to a range of dates
    ([``start_at``, ``ends_at``]) and for at least one field to match a search
    term (``q``).

    Query results can be ordered by natural fields (``o``) in either ascending
    or descending order (``ot``).

    **Tags: billing

    **Examples

    .. code-block:: http

        GET /api/billing/charges?start_at=2015-07-05T07:00:00.000Z\
&o=date&ot=desc HTTP/1.1

    Retrieves the list of charges that were created before
    2015-07-05T07:00:00.000Z, sort them by date in descending order.

    responds

    .. code-block:: json

        {
            "count": 1,
            "unit": "usd",
            "total": "112120",
            "next": null,
            "previous": null,
            "results": [{
                "created_at": "2016-01-01T00:00:02Z",
                "readable_amount": "$1121.20",
                "amount": 112120,
                "unit": "usd",
                "description": "Charge for subscription to cowork open-space",
                "last4": "1234",
                "exp_date": "12/2016",
                "processor_key": "ch_XAb124EF",
                "state": "DONE"
            }]
        }
    """
    serializer_class = ChargeSerializer
    pagination_class = TotalPagination


class OrganizationChargeQuerysetMixin(OrganizationMixin):

    def get_queryset(self):
        return Charge.objects.by_customer(self.organization)


class OrganizationChargeListAPIView(SmartChargeListMixin,
                                    OrganizationChargeQuerysetMixin,
                                    ListAPIView):

    """
    List all ``Charge`` for a subscriber.

    **Tags: billing

    **Examples

    .. code-block:: http

         GET /api/charges?start_at=2015-07-05T07:00:00.000Z\
&o=date&ot=desc HTTP/1.1

    .. code-block:: json

        {
            "count": 1,
            "unit": "usd",
            "total": "112120",
            "next": null,
            "previous": null,
            "results": [{
                "created_at": "2016-01-01T00:00:03Z",
                "readable_amount": "$1121.20",
                "amount": 112120,
                "unit": "usd",
                "description": "Charge for subscription to cowork open-space",
                "last4": "1234",
                "exp_date"" "12/2016",
                "processor_key": "ch_XAb124EF",
                "state": "DONE"
            } ...]
    """
    serializer_class = ChargeSerializer
    pagination_class = TotalPagination


class ChargeRefundAPIView(RetrieveChargeMixin, CreateAPIView):
    """
    Refunds a processor charge

    Partially or totally refund all or a subset of line items on a ``Charge``.

    **Tags: billing

    **Example

    .. code-block:: http

        POST /api/billing/charges/ch_XAb124EF/refund/ HTTP/1.1

    .. code-block:: json

        {
            "lines": [
              {
                  "num": 0,
                  "refunded_amount": 4000
              },
              {
                  "num": 1,
                  "refunded_amount": 82120
              }
          ]
        }

    Refunds $40 and $821.20 from first and second line item on the receipt
    respectively. The API call responds with the Charge.

    responds

    .. code-block:: json

        {
            "created_at": "2016-01-01T00:00:05Z",
            "readable_amount": "$1121.20",
            "amount": 112120,
            "unit": "usd",
            "description": "Charge for subscription to cowork open-space",
            "last4": "1234",
            "exp_date": "12/2016",
            "processor_key": "ch_XAb124EF",
            "state": "DONE"
        }
    """
    serializer_class = RefundChargeSerializer

    @swagger_auto_schema(responses={
        200: OpenAPIResponse("Refund successful", ChargeSerializer),
        400: OpenAPIResponse("parameters error", ValidationErrorSerializer)})
    def post(self, request, *args, **kwargs): #pylint: disable=unused-argument
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.object = self.get_object()
        charge = self.object
        if charge.state != charge.DONE:
            if charge.state == charge.DISPUTED:
                msg = _("You cannot refund a disputed charge.")
            elif charge.state == charge.CREATED:
                msg = _("You cannot refund a pending charge.")
            else:
                msg = _("You cannot refund a failed charge.")
            return Response({"detail": msg},
                status=status.HTTP_405_METHOD_NOT_ALLOWED)
        with transaction.atomic():
            try:
                for line in serializer.validated_data.get('lines', []):
                    try:
                        self.object.refund(int(line['num']),
                            refunded_amount=int(line.get('refunded_amount', 0)),
                            user=request.user)
                    except ValueError:
                        raise Http404(
                         _("Unable to retrieve line '%(lineno)s' in %(charge)s")
                            % {'lineno': line, 'charge': self.object})
            except InsufficientFunds as insufficient_funds_err:
                return Response({"detail": str(insufficient_funds_err)},
                    status=status.HTTP_405_METHOD_NOT_ALLOWED)
        return Response(ChargeSerializer().to_representation(self.object))


class EmailChargeReceiptAPIView(RetrieveChargeMixin, GenericAPIView):
    """
    Re-sends a charge receipt

    Email the charge receipt to the customer email address on file.

    The service sends a duplicate e-mail receipt for charge `ch_XAb124EF`
    to the e-mail address of the customer, i.e. `joe@localhost.localdomain`.

    **Tags: billing

    **Examples

    .. code-block:: http

        POST /api/billing/charges/ch_XAb124EF/email/  HTTP/1.1

    responds

    .. code-block:: json

        {
            "charge_id": "ch_XAb124EF",
            "email": "joe@localhost.localdomain"
        }

    """
    serializer_class = EmailChargeReceiptSerializer

    def post(self, request, *args, **kwargs): #pylint: disable=unused-argument
        self.object = self.get_object()
        signals.charge_updated.send(
            sender=__name__, charge=self.object, user=request.user)
        return Response(self.get_serializer().to_representation({
            "charge_id": self.object.processor_key,
            "email": self.object.customer.email}))
