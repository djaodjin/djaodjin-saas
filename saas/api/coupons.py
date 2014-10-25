# Copyright (c) 2014, DjaoDjin inc.
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
from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.generics import (GenericAPIView,
    ListCreateAPIView, RetrieveUpdateDestroyAPIView)
from rest_framework.response import Response
from extra_views.contrib.mixins import SearchableListMixin, SortableListMixin

from saas.models import CartItem, Coupon
from saas.mixins import ProviderMixin
from saas.utils import datetime_or_now

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

    code = serializers.CharField()


class CouponMixin(ProviderMixin):

    model = Coupon
    serializer_class = CouponSerializer
    slug_field = 'code'
    slug_url_kwarg = 'coupon'

    def get_queryset(self):
        queryset = super(CouponMixin, self).get_queryset()
        return queryset.filter(organization=self.get_organization())

    def pre_save(self, obj):
        """
        Force organization to the one that can be retrieved from the URL.
        """
        obj.organization = self.get_organization()
        return super(CouponMixin, self).pre_save(obj)


class SmartCouponListMixin(SearchableListMixin, SortableListMixin):
    """
    Subscriber list which is also searchable and sortable.
    """
    search_fields = ['created_at',
                     'code',
                     'description',
                     'percent',
                     'ends_at',
                     'organization__full_name']

    sort_fields_aliases = [('code', 'code'),
                           ('percent', 'percent'),
                           ('ends_at', 'ends_at'),
                           ('description', 'description'),
                           ('created_at', 'created_at')]


class CouponListAPIView(SmartCouponListMixin, CouponMixin, ListCreateAPIView):

    def post(self, request, *args, **kwargs): #pylint: disable=unused-argument
        return super(CouponListAPIView, self).post(request, *args, **kwargs)


class CouponDetailAPIView(CouponMixin, RetrieveUpdateDestroyAPIView):

    pass


class CouponRedeemAPIView(GenericAPIView):
    """
.. http:post:: /api/cart/redeem/

    Redeem a ``Coupon`` and apply the discount to the eligible items
    in the cart.

   **Example request**:

   .. sourcecode:: http

    {
        "code": "LABORDAY"
    }

   **Example response**:

   .. sourcecode:: http

    {
        "details": "Coupon 'LABORDAY' was successfully applied."
    }
    """
    serializer_class = RedeemCouponSerializer

    @staticmethod
    def redeem(request, coupon_code):
        now = datetime_or_now()
        coupon_applied = False
        for item in CartItem.objects.get_cart(request.user):
            coupon = Coupon.objects.filter(
                Q(ends_at__isnull=True) | Q(ends_at__gt=now),
                code__iexact=coupon_code, # case incensitive search.
                organization=item.plan.organization).first()
            if coupon and (not coupon.plan or (coupon.plan == item.plan)):
                # Coupon can be restricted to a plan or apply to all plans
                # of an organization.
                coupon_applied = True
                item.coupon = coupon
                item.save()
        return coupon_applied

    def post(self, request, *args, **kwargs): #pylint: disable=unused-argument
        serializer = self.get_serializer(data=request.DATA, files=request.FILES)
        if serializer.is_valid():
            coupon_code = serializer.data['code']
            if self.redeem(request, coupon_code):
                details = {"details": (
                        "Coupon '%s' was successfully applied." % coupon_code)}
                headers = {}
                # XXX does not show details since we reload in djaodjin-saas.
                messages.success(request, details['details'])
                return Response(details, status=status.HTTP_200_OK,
                                headers=headers)
            else:
                details = {"details": (
"No items can be discounted using this coupon: %s." % coupon_code)}
                return Response(details, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
