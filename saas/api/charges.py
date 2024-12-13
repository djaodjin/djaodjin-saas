# Copyright (c) 2024, DjaoDjin inc.
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
from django.db.models import Sum
from rest_framework import generics, mixins, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .serializers import (ChargeSerializer, CheckoutSerializer,
    EmailChargeReceiptSerializer, PaymentSerializer, RefundChargeSerializer,
    ValidationDetailSerializer)
from .. import signals
from ..backends import ProcessorError
from ..compat import is_authenticated, gettext_lazy as _, reverse
from ..docs import OpenApiResponse, extend_schema
from ..filters import DateRangeFilter, OrderingFilter, SearchFilter
from ..humanize import as_money
from ..models import Charge, InsufficientFunds, get_broker
from ..mixins import ChargeMixin, DateRangeContextMixin, OrganizationMixin
from ..pagination import TotalPagination
from ..utils import build_absolute_uri


class ChargeResourceView(ChargeMixin, generics.RetrieveAPIView):
    """
    Retrieves a processor charge

    Pass through to the processor and returns details about a ``Charge``.

    **Tags**: billing, subscriber, chargemodel

    **Examples**

    .. code-block:: http

        GET /api/billing/xia/charges/ch_XAb124EF HTTP/1.1

    responds

    .. code-block:: json

        {
            "created_at": "2016-01-01T00:00:01Z",
            "readable_amount": "$1121.20",
            "amount": 112120,
            "unit": "usd",
            "description": "Charge for subscription to cowork open-space",
            "last4": "1234",
            "exp_date": "2016-06-01",
            "processor_key": "ch_XAb124EF",
            "state": "DONE"
        }
    """
    serializer_class = ChargeSerializer


class SmartChargeListMixin(DateRangeContextMixin):
    """
    Subscriber list which is also searchable and sortable.
    """
    search_fields = (
        'description',
        'processor_key',
        'customer__full_name'
    )
    ordering_fields = (
        ('description', 'description'),
        ('amount', 'amount'),
        ('customer__full_name', 'Full name'),
        ('created_at', 'created_at')
    )
    ordering = ('created_at',)

    filter_backends = (DateRangeFilter, SearchFilter, OrderingFilter)


class ChargeQuerysetMixin(object):

    def get_queryset(self):
        return Charge.objects.all()


class ChargeListAPIView(SmartChargeListMixin,
                        ChargeQuerysetMixin, generics.ListAPIView):
    """
    Lists processor charges

    Returns a list of {{PAGE_SIZE}} charges that were created on the payment
    processor (ex: Stripe).

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    **Tags**: billing, list, broker, chargemodel

    **Examples**

    .. code-block:: http

        GET /api/billing/charges?start_at=2015-07-05T07:00:00.000Z\
&o=date&ot=desc HTTP/1.1

    Retrieves the list of charges that were created before
    2015-07-05T07:00:00.000Z, sort them by date in descending order.

    responds

    .. code-block:: json

        {
            "count": 1,
            "balance_amount": "112120",
            "balance_unit": "usd",
            "next": null,
            "previous": null,
            "results": [{
                "created_at": "2016-01-01T00:00:02Z",
                "readable_amount": "$1121.20",
                "amount": 112120,
                "unit": "usd",
                "description": "Charge for subscription to cowork open-space",
                "last4": "1234",
                "exp_date": "2016-06-01",
                "processor_key": "ch_XAb124EF",
                "state": "DONE"
            }]
        }
    """
    serializer_class = ChargeSerializer
    pagination_class = TotalPagination

    def get_queryset(self):
        queryset = super(ChargeListAPIView, self).get_queryset()
        #pylint:disable=attribute-defined-outside-init
        self.totals = queryset.values('unit').annotate(amount=Sum('amount'))
        return queryset


class OrganizationChargeQuerysetMixin(OrganizationMixin):

    def get_queryset(self):
        return Charge.objects.by_customer(self.organization)


class OrganizationChargeListAPIView(SmartChargeListMixin,
                                    OrganizationChargeQuerysetMixin,
                                    generics.ListAPIView):

    """
    Lists all charges for a subscriber

    **Tags**: billing

    **Examples**

    .. code-block:: http

         GET /api/billing/xia/charges?start_at=2015-07-05T07:00:00.000Z\
&o=date&ot=desc HTTP/1.1

    .. code-block:: json

        {
            "count": 1,
            "unit": "usd",
            "balance_amount": "112120",
            "balance_unit": "usd",
            "next": null,
            "previous": null,
            "results": [{
                "created_at": "2016-01-01T00:00:03Z",
                "readable_amount": "$1121.20",
                "amount": 112120,
                "unit": "usd",
                "description": "Charge for subscription to cowork open-space",
                "last4": "1234",
                "exp_date": "2016-06-01",
                "processor_key": "ch_XAb124EF",
                "state": "DONE"
            } ...]
    """
    serializer_class = ChargeSerializer
    pagination_class = TotalPagination


class ChargeRefundAPIView(ChargeMixin, generics.CreateAPIView):
    """
    Refunds a processor charge

    Partially or totally refund all or a subset of line items on a ``Charge``.

    **Tags**: billing, provider, chargemodel

    **Examples**

    .. code-block:: http

        POST /api/billing/xia/charges/ch_XAb124EF/refund HTTP/1.1

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
            "exp_date": "2016-06-01",
            "processor_key": "ch_XAb124EF",
            "state": "DONE"
        }
    """
    serializer_class = RefundChargeSerializer

    @extend_schema(responses={
        200: OpenApiResponse(ChargeSerializer),
        400: OpenApiResponse(ValidationDetailSerializer)})
    def post(self, request, *args, **kwargs): #pylint: disable=unused-argument
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        #pylint:disable=attribute-defined-outside-init
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
        refunded_amount = 0
        with transaction.atomic():
            try:
                for line in serializer.validated_data.get('lines', []):
                    try:
                        line_refunded_amount = int(line.get(
                            'refunded_amount', 0))
                        self.object.refund(int(line['num']),
                            refunded_amount=line_refunded_amount,
                            user=request.user)
                        refunded_amount += line_refunded_amount
                    except ValueError:
                        raise Http404(
                         _("Unable to retrieve line '%(lineno)s' in %(charge)s")
                            % {'lineno': line, 'charge': self.object})
            except InsufficientFunds as insufficient_funds_err:
                return Response({"detail": str(insufficient_funds_err)},
                    status=status.HTTP_405_METHOD_NOT_ALLOWED)
        self.object.detail = _("%(amount)s refunded successfully"\
" on charge %(charge_id)s.") % {
            'amount': as_money(refunded_amount, self.object.unit),
            'charge_id': self.object.processor_key
        }
        return Response(ChargeSerializer().to_representation(self.object))


class EmailChargeReceiptAPIView(ChargeMixin, generics.GenericAPIView):
    """
    Re-sends a charge receipt

    Email the charge receipt to the customer email address on file.

    The service sends a duplicate e-mail receipt for charge `ch_XAb124EF`
    to the e-mail address of the customer, i.e. `joe@localhost.localdomain`.

    **Tags**: billing, subscriber, chargemodel

    **Examples**

    .. code-block:: http

        POST /api/billing/xia/charges/ch_XAb124EF/email  HTTP/1.1

    responds

    .. code-block:: json

        {
            "charge_id": "ch_XAb124EF",
            "email": "joe@localhost.localdomain"
        }

    """
    serializer_class = EmailChargeReceiptSerializer

    @extend_schema(request=None)
    def post(self, request, *args, **kwargs): #pylint: disable=unused-argument
        #pylint:disable=attribute-defined-outside-init
        self.object = self.get_object()
        signals.charge_updated.send(
            sender=__name__, charge=self.object, user=request.user)
        return Response(self.get_serializer().to_representation({
            'charge_id': self.object.processor_key,
            'email': self.object.customer.email,
            'detail': _("A copy of the receipt was sent to %(email)s.") % {
                'email': self.object.customer.email}}))


class PaymentDetailAPIView(mixins.CreateModelMixin, generics.RetrieveAPIView):
    """
    Retrieves a processor charge

    Pass through to the processor and returns details about a ``Charge``.

    **Tags**: billing, subscriber, chargemodel

    **Examples**

    .. code-block:: http

        GET /api/payments/ch_XAb124EF HTTP/1.1

    responds

    .. code-block:: json

        {
            "created_at": "2016-01-01T00:00:01Z",
            "readable_amount": "$1121.20",
            "amount": 112120,
            "unit": "usd",
            "description": "Charge for subscription to cowork open-space",
            "last4": "1234",
            "exp_date": "2016-06-01",
            "processor_key": "ch_XAb124EF",
            "state": "DONE"
        }
    """
    model = Charge
    lookup_field = 'claim_code'
    queryset = Charge.objects.all()
    serializer_class = PaymentSerializer

    def get_serializer_class(self):
        if self.request.method.lower() in ('post',):
            return CheckoutSerializer
        return super(PaymentDetailAPIView, self).get_serializer_class()

    def get_object(self):
        instance = super(PaymentDetailAPIView, self).get_object()
        instance.results = instance.line_items_grouped_by_subscription
        instance.retrieve() # This will settle the charge on the processor
                            # if necessary.
        if instance.state == instance.CREATED:
            provider = instance.broker
            # XXX OK to override Charge.processor?
            instance.processor_info = \
                provider.processor_backend.get_payment_context(
                    instance.customer,
                    amount=instance.amount,
                    unit=instance.unit,
                    broker_fee_amount=instance.broker_fee_amount,
                    provider=provider, broker=get_broker())
        return instance

    @extend_schema(request=None)
    def post(self, request, *args, **kwargs):
        """
        Pay an invoice

        Pay an invoice.

        **Tags**: billing, provider, chargemodel

        **Examples**

        .. code-block:: http

            POST /api/payments/ch_XAb124EF HTTP/1.1

        .. code-block:: json

            {
                "processor_token": "tok_23prgoqpstf56todq"
            }

        responds

        .. code-block:: json

           {
                "created_at": "2016-06-21T23:42:44.270977Z",
                "processor_key": "pay_5lK5TacFH3gbKe",
                "amount": 2000,
                "unit": "usd",
                "description": "Charge pay_5lK5TacFH3gblP on credit card \
of Xia",
                "last4": "1234",
                "exp_date": "2016-06-01",
                "state": "created"
            }
        """
        return self.create(request, *args, **kwargs)

    def get_success_headers(self, data):
        return {'Location': build_absolute_uri(
            self.request, reverse('saas_payment', kwargs=self.kwargs))}

    def perform_create(self, serializer):
        processor_token = serializer.validated_data.get('processor_token')
        remember_card = False
        if is_authenticated(self.request):
            # We won't remember the card if the user is not authenticated.
            remember_card = serializer.validated_data.get('remember_card')
        charge = self.get_object()
        try:
            with transaction.atomic():
                charge.execute(processor_token, self.request.user,
                    remember_card=remember_card)
        except ProcessorError as err:
            raise ValidationError(err)
