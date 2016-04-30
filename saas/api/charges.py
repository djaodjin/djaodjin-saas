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

from collections import OrderedDict

from django.http import Http404
from django.db import transaction
from extra_views.contrib.mixins import SearchableListMixin, SortableListMixin
from rest_framework import status, serializers
from rest_framework.generics import ListAPIView, GenericAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .. import signals
from ..models import Charge, InsufficientFunds
from ..mixins import ChargeMixin, DateRangeMixin

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


class ChargeSerializer(serializers.ModelSerializer):

    state = serializers.CharField(source='get_state_display')

    class Meta:
        model = Charge
        fields = ('created_at', 'amount', 'unit', 'description',
                  'last4', 'exp_date', 'processor_key', 'state')


class ChargeResourceView(RetrieveChargeMixin, RetrieveAPIView):
    """
    Pass through to the processor and returns details about a ``Charge``.

    **Example response**:

    .. sourcecode:: http

        {
            "created_at": "2016-01-01T00:00:00Z",
            "amount": 112120,
            "unit": "usd",
            "description": "Charge for subscription to cowork open-space",
            "last4": "1234",
            "exp_date"" "12/2016",
            "processor_key": "ch_XAb124EF",
            "state": "DONE"
        }
    """
    serializer_class = ChargeSerializer


class TotalPagination(PageNumberPagination):

    def paginate_queryset(self, queryset, request, view=None):
        self.total = 0
        for charge in queryset:
            self.total += charge.amount
        return super(TotalPagination, self).paginate_queryset(
            queryset, request, view=view)

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('total', self.total),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


class SmartChargeListMixin(SortableListMixin, DateRangeMixin,
                           SearchableListMixin):
    """
    Subscriber list which is also searchable and sortable.
    """
    search_fields = ['descr',
                     'processor_key',
                     'customer__full_name']

    sort_fields_aliases = [('descr', 'description'),
                           ('amount', 'amount'),
                           ('customer__full_name', 'Full name')]


class ChargeQuerysetMixin(object):

    @staticmethod
    def get_queryset():
        return Charge.objects.all()


class ChargeListAPIView(SmartChargeListMixin,
                        ChargeQuerysetMixin, ListAPIView):

    """
    List of ``Charge``.

    **Example request**:

    .. sourcecode:: http

        GET /api/charges?start_at=2015-07-05T07:00:00.000Z\
&o=date&ot=desc

    **Example response**:

    .. sourcecode:: http

        {
            "count": 1,
            "unit": "usd",
            "total": "112120",
            "next": null,
            "previous": null,
            "results": [{
                "created_at": "2016-01-01T00:00:00Z",
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


class ChargeRefundAPIView(RetrieveChargeMixin, RetrieveAPIView):
    """
    Partially or totally refund all or a subset of line items on a ``Charge``.

    **Example request**:

    .. sourcecode:: http

        POST /api/billing/charges/ch_XAb124EF/refund/

        {
            "lines": [
              {
                  "num": 0,
                  "refunded_amount": 4000,
              },
              {
                  "num": 1,
                  "refunded_amount": 82120,
              }
          ]
        }

    **Example response**:

    .. sourcecode:: http

        {
            "created_at": "2016-01-01T00:00:00Z",
            "amount": 112120,
            "unit": "usd",
            "description": "Charge for subscription to cowork open-space",
            "last4": "1234",
            "exp_date"" "12/2016",
            "processor_key": "ch_XAb124EF",
            "state": "DONE"
        }
    """
    serializer_class = ChargeSerializer

    def post(self, request, *args, **kwargs): #pylint: disable=unused-argument
        self.object = self.get_object()
        with transaction.atomic():
            try:
                for line in request.data.get('lines', []):
                    try:
                        self.object.refund(int(line['num']),
                            refunded_amount=int(line.get('refunded_amount', 0)),
                            user=request.user)
                    except ValueError:
                        raise Http404("Unable to retrieve line '%s' in %s"
                            % (line, self.object))
            except InsufficientFunds as insufficient_funds_err:
                return Response({"detail": str(insufficient_funds_err)},
                    status=status.HTTP_405_METHOD_NOT_ALLOWED)
        return super(ChargeRefundAPIView, self).get(request, *args, **kwargs)


class EmailChargeReceiptAPIView(RetrieveChargeMixin, GenericAPIView):
    """
    Email the charge receipt to the customer email address on file.

    **Example response**:

    .. sourcecode:: http

        {
            "charge_id": "ch_XAb124EF",
            "email": "info@djaodjin.com"
        }
    """
    def post(self, request, *args, **kwargs): #pylint: disable=unused-argument
        self.object = self.get_object()
        signals.charge_updated.send(
            sender=__name__, charge=self.object, user=request.user)
        return Response({
            "charge_id": self.object.processor_key,
            "email": self.object.customer.email})
