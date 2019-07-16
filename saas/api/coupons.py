# Copyright (c) 2018, DjaoDjin inc.
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

from rest_framework import serializers
from rest_framework.generics import (ListCreateAPIView,
    RetrieveUpdateDestroyAPIView)

from ..filters import OrderingFilter, SearchFilter, DateRangeFilter
from ..models import Coupon
from ..mixins import CouponMixin, ProviderMixin

#pylint: disable=no-init
#pylint: disable=old-style-class


class CouponSerializer(serializers.ModelSerializer):

    class Meta:
        model = Coupon
        fields = ('code', 'percent', 'created_at', 'ends_at', 'description')


class SmartCouponListMixin(object):
    """
    ``Coupon`` list which is also searchable and sortable.
    """
    search_fields = ('code',
                     'description',
                     'percent',
                     'organization__full_name')

    ordering_fields = [('code', 'code'),
                           ('created_at', 'created_at'),
                           ('description', 'description'),
                           ('ends_at', 'ends_at'),
                           ('percent', 'percent')]

    filter_backends = (OrderingFilter, SearchFilter)


class CouponQuerysetMixin(ProviderMixin):

    def get_queryset(self):
        return Coupon.objects.filter(organization=self.organization)


class CouponListCreateAPIView(SmartCouponListMixin, CouponQuerysetMixin,
                              ListCreateAPIView):
    """
    Lists discount codes

    Queries a page (``PAGE_SIZE`` records) of ``Coupon`` associated
    to a provider.

    The queryset can be filtered to a range of dates
    ([``start_at``, ``ends_at``]) and for at least one field to match a search
    term (``q``).

    Query results can be ordered by natural fields (``o``) in either ascending
    or descending order (``ot``).

    **Tags: billing

    **Examples

    .. code-block:: http

        GET /api/billing/cowork/coupons?o=code&ot=asc&q=DIS HTTP/1.1

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
                    "percent": 100,
                    "created_at": "2014-01-01T09:00:00Z",
                    "ends_at": null,
                    "description": null
                },
                {
                    "code": "DIS50",
                    "percent": 50,
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

    def post(self, request, *args, **kwargs):
        """
        Creates a discount code

        Customers will be able to use the `code` until `ends_at`
        to subscribe to plans from the Coupon's provider at a discount.

        **Examples

        .. code-block:: http

            POST /api/billing/cowork/coupons HTTP/1.1

        .. code-block:: json

            {
              "code": "DIS100",
              "percent": 100,
              "ends_at": null,
              "description": null
            }

        responds

        .. code-block:: json

            {
              "code": "DIS100",
              "percent": 100,
              "ends_at": null,
              "description": null
            }
        """
        return self.create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(organization=self.organization)



class CouponDetailAPIView(CouponMixin, RetrieveUpdateDestroyAPIView):
    """
    Retrieves a discount code

    **Tags: billing

    **Examples

    .. code-block:: http

        GET /api/billing/cowork/coupons/DIS100 HTTP/1.1

    responds

    .. code-block:: json

        {
            "code": "DIS100",
            "percent": 100,
            "created_at": "2014-01-01T09:00:00Z",
            "ends_at": null,
            "description": null
       }
    """
    serializer_class = CouponSerializer

    def put(self, request, *args, **kwargs):
        """
        Updates a discount code

        **Tags: billing

        **Examples

        .. code-block:: http

            PUT /api/billing/cowork/coupons/DIS100 HTTP/1.1

        .. code-block:: json

            {
                "percent": 100,
                "ends_at": null,
                "description": null
            }

        responds

        .. code-block:: json

            {
                "percent": 100,
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

        **Tags: billing

        **Examples

        .. code-block:: http

            DELETE /api/billing/cowork/coupons/DIS100 HTTP/1.1
        """
        return self.destroy(request, *args, **kwargs)

    def get_object(self):
        return self.coupon

    def perform_update(self, serializer):
        if serializer.validated_data.get('ends_at', None):
            serializer.save(organization=self.organization)
        else:
            serializer.save(organization=self.organization, ends_at='never')
