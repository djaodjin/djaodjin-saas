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

from django.contrib import messages
from rest_framework import serializers, status
from rest_framework.generics import (GenericAPIView,
    ListCreateAPIView, RetrieveUpdateDestroyAPIView)
from rest_framework.response import Response
from extra_views.contrib.mixins import SearchableListMixin, SortableListMixin

from ..filters import SortableDateRangeSearchableFilterBackend
from ..models import CartItem, Coupon
from ..mixins import CouponMixin, ProviderMixin

#pylint: disable=no-init
#pylint: disable=old-style-class


class CouponSerializer(serializers.ModelSerializer):

    class Meta:
        model = Coupon
        fields = ('code', 'percent', 'created_at', 'ends_at', 'description')


class RedeemCouponSerializer(serializers.Serializer):
    """
    Serializer to redeem a ``Coupon``.
    """

    code = serializers.CharField(help_text="Coupon code to redeem")

    def create(self, validated_data):
        return validated_data

    def update(self, instance, validated_data):
        raise RuntimeError('`update()` should not have been called.')


class SmartCouponListMixin(SortableListMixin, SearchableListMixin):
    """
    ``Coupon`` list which is also searchable and sortable.
    """
    search_fields = ['code',
                     'description',
                     'percent',
                     'organization__full_name']

    search_date_fields = ['created_at', 'ends_at']

    sort_fields_aliases = [('code', 'code'),
                           ('created_at', 'created_at'),
                           ('description', 'description'),
                           ('ends_at', 'ends_at'),
                           ('percent', 'percent')]

    filter_backends = (SortableDateRangeSearchableFilterBackend(
        sort_fields_aliases, search_fields),)


class CouponQuerysetMixin(ProviderMixin):

    def get_queryset(self):
        return Coupon.objects.filter(organization=self.organization)


class CouponListAPIView(SmartCouponListMixin, CouponQuerysetMixin,
                        ListCreateAPIView):
    """
    Queries a page (``PAGE_SIZE`` records) of ``Coupon`` associated
    to a provider.

    The queryset can be filtered to a range of dates
    ([``start_at``, ``ends_at``]) and for at least one field to match a search
    term (``q``).

    Query results can be ordered by natural fields (``o``) in either ascending
    or descending order (``ot``).

    **Examples

    .. code-block:: http

        GET /api/billing/cowork/coupons?o=code&ot=asc&q=DIS HTTP/1.1

    retrieves the list of Coupon for provider cowork where `code`
    matches 'DIS', ordered by `code` in ascending order.

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

    def post(self, request, *args, **kwargs):
        """
        Creates a ``Coupon`` to be used on provider's plans.

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
        """
        return self.create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(organization=self.organization)



class CouponDetailAPIView(CouponMixin, RetrieveUpdateDestroyAPIView):
    """
    Retrieves a ``Coupon``.

    **Examples

    .. code-block:: http

        GET /api/billing/cowork/coupons/DIS100 HTTP/1.1

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
        Updates a ``Coupon``.

        **Examples

        .. code-block:: http

            PUT /api/billing/cowork/coupons/DIS100 HTTP/1.1

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
        Deletes a ``Coupon``.

        **Examples

        .. code-block:: http

            DELETE /api/billing/cowork/coupons/DIS100 HTTP/1.1
        """
        return self.destroy(request, *args, **kwargs)

    def get_object(self):
        return self.coupon

    def perform_update(self, serializer):
        if 'ends_at' in serializer.validated_data:
            serializer.save(organization=self.organization)
        else:
            serializer.save(organization=self.organization, ends_at='never')


class CouponRedeemAPIView(GenericAPIView):
    """
    Redeem a ``Coupon`` and apply the discount to the eligible items
    in the cart.

    **Examples

    .. code-block:: http

         POST /api/redeem HTTP/1.1

    .. code-block:: json

        {
            "code": "LABORDAY"
        }

    responds

    .. code-block:: json

        {
            "details": "Coupon 'LABORDAY' was successfully applied."
        }
    """
    serializer_class = RedeemCouponSerializer

    def post(self, request, *args, **kwargs): #pylint: disable=unused-argument
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            coupon_code = serializer.data['code']
            if CartItem.objects.redeem(request.user, coupon_code):
                details = {"details": (
                        "Coupon '%s' was successfully applied." % coupon_code)}
                headers = {}
                # XXX Django 1.7: 500 error, argument must be an HttpRequest
                # object, not 'Request'. Not an issue with Django 1.6.2
                # Since we rely on the message to appear after reload of
                # the cart page in the casperjs tests, we can't get rid
                # of this statement just yet.
                messages.success(request._request, details['details'])#pylint: disable=protected-access
                return Response(details, status=status.HTTP_200_OK,
                                headers=headers)
            details = {"details": (
"No items can be discounted using this coupon: %s." % coupon_code)}
            return Response(details, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
