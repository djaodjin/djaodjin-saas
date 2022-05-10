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
from __future__ import unicode_literals

from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import (ListCreateAPIView,
    RetrieveUpdateDestroyAPIView)
from rest_framework.response import Response

from .serializers import CouponSerializer, CouponCreateSerializer
from ..compat import gettext_lazy as _
from ..docs import swagger_auto_schema, OpenAPIResponse
from ..filters import OrderingFilter, SearchFilter, DateRangeFilter
from ..models import Coupon
from ..mixins import CouponMixin, ProviderMixin
from ..utils import handle_uniq_error

#pylint: disable=no-init


class SmartCouponListMixin(object):
    """
    ``Coupon`` list which is also searchable and sortable.
    """
    search_fields = (
        'code',
        'description',
        'amount',
        'organization__full_name'
    )
    ordering_fields = (
        ('code', 'code'),
        ('created_at', 'created_at'),
        ('description', 'description'),
        ('ends_at', 'ends_at'),
        ('discount_type', 'discount_type'),
        ('amount', 'amount')
    )
    ordering = ('ends_at',)

    filter_backends = (OrderingFilter, SearchFilter)


class CouponQuerysetMixin(ProviderMixin):

    def get_queryset(self):
        return Coupon.objects.filter(organization=self.organization)


class CouponListCreateAPIView(SmartCouponListMixin, CouponQuerysetMixin,
                              ListCreateAPIView):
    """
    Lists discount codes

    Returns a list of {{PAGE_SIZE}} coupons for provider {organization}.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    The API is typically used within an HTML
    `coupons page </docs/themes/#dashboard_billing_coupons>`_
    as present in the default theme.

    **Tags**: billing, provider, couponmodel

    **Examples**

    .. code-block:: http

        GET /api/billing/cowork/coupons/?o=code&ot=asc&q=DIS HTTP/1.1

    retrieves the list of Coupon for provider cowork where `code`
    matches 'DIS', ordered by `code` in ascending order.

    responds

    .. code-block:: json

        {
            "count": 2,
            "next": null,
            "previous": null,
            "results": [
                {
                    "code": "DIS100",
                    "discount_type": "percentage",
                    "discount_value": 10000,
                    "created_at": "2014-01-01T09:00:00Z",
                    "ends_at": null,
                    "description": null
                },
                {
                    "code": "DIS50",
                    "discount_type": "percentage",
                    "discount_value": 5000,
                    "created_at": "2014-01-01T09:00:00Z",
                    "ends_at": null,
                    "description": null
                }
            ]
        }
    """
    serializer_class = CouponSerializer
    filter_backends = (SmartCouponListMixin.filter_backends +
        (DateRangeFilter,))

    def get_serializer_class(self):
        if self.request.method.lower() in ('post',):
            return CouponCreateSerializer
        return super(CouponListCreateAPIView, self).get_serializer_class()

    @swagger_auto_schema(responses={
        201: OpenAPIResponse("created", CouponSerializer)})
    def post(self, request, *args, **kwargs):
        """
        Creates a discount code

        Customers will be able to use the `code` until `ends_at`
        to subscribe to plans from the Coupon's provider at a discount.

        The API is typically used within an HTML
        `coupons page </docs/themes/#dashboard_billing_coupons>`_
        as present in the default theme.

        **Tags**: billing, provider, couponmodel

        **Examples**

        .. code-block:: http

            POST /api/billing/cowork/coupons/ HTTP/1.1

        .. code-block:: json

            {
              "code": "DIS100",
              "discount_type": "percentage",
              "discount_value": 10000,
              "ends_at": null,
              "description": null
            }

        responds

        .. code-block:: json

            {
              "code": "DIS100",
              "discount_type": "percentage",
              "discount_value": 10000,
              "ends_at": null,
              "description": null
            }
        """
        return self.create(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        #pylint:disable=unused-argument
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # check plan belongs to organization
        plan = serializer.validated_data.get('plan')
        if plan and plan.organization != self.organization:
            raise ValidationError(
                _("The plan does not belong to the organization."))
        try:
            serializer.save(organization=self.organization)
        except IntegrityError as err:
            handle_uniq_error(err)
        headers = self.get_success_headers(serializer.data)
        return Response(CouponSerializer().to_representation(
            serializer.instance), status=status.HTTP_201_CREATED,
            headers=headers)


class CouponDetailAPIView(CouponMixin, RetrieveUpdateDestroyAPIView):
    """
    Retrieves a discount code

    The API is typically used within an HTML
    `coupons page </docs/themes/#dashboard_billing_coupons>`_
    as present in the default theme.

    **Tags**: billing, provider, couponmodel

    **Examples**

    .. code-block:: http

        GET /api/billing/cowork/coupons/DIS100/ HTTP/1.1

    responds

    .. code-block:: json

        {
            "code": "DIS100",
            "discount_type": "percentage",
            "discount_value": 10000,
            "created_at": "2014-01-01T09:00:00Z",
            "ends_at": null,
            "description": null
       }
    """
    serializer_class = CouponSerializer

    def put(self, request, *args, **kwargs):
        """
        Updates a discount code

        The API is typically used within an HTML
        `coupons page </docs/themes/#dashboard_billing_coupons>`_
        as present in the default theme.

        **Tags**: billing, provider, couponmodel

        **Examples**

        .. code-block:: http

            PUT /api/billing/cowork/coupons/DIS100/ HTTP/1.1

        .. code-block:: json

            {
                "discount_type": "percentage",
                "discount_value": 10000,
                "ends_at": null,
                "description": null
            }

        responds

        .. code-block:: json

            {
                "code": "DIS100",
                "discount_type": "percentage",
                "discount_value": 10000,
                "ends_at": null,
                "description": null
            }
        """
        return self.update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        """
        Deletes a discount code

        Only coupons which have never been applied to an oder will
        be permanently deleted. Coupons which have already be used
        at least once will be de-activated and still available for
        performance measurements.

        The API is typically used within an HTML
        `coupons page </docs/themes/#dashboard_billing_coupons>`_
        as present in the default theme.

        **Tags**: billing, provider, couponmodel

        **Examples**

        .. code-block:: http

            DELETE /api/billing/cowork/coupons/DIS100/ HTTP/1.1
        """
        return self.destroy(request, *args, **kwargs)

    def get_object(self):
        return self.coupon

    def perform_update(self, serializer):
        if serializer.validated_data.get('ends_at', None):
            serializer.save(organization=self.organization)
        else:
            serializer.save(organization=self.organization, ends_at='never')
