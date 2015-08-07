# Copyright (c) 2015, DjaoDjin inc.
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

"""
Add and remove plans from a user subscription cart.

.. http:post:: /api/cart/

    Add a ``Plan`` into the subscription cart of a ``User``.

   **Example request**:

   .. sourcecode:: http

    {
        "plan": "premium",
    }

   **Example response**:

   .. sourcecode:: http

    {
        "plan": "premium",
    }

.. http:delete:: /api/cart/:plan

    Remove a ``Plan`` from the subscription cart of a ``User``.

   **Example request**:

   .. sourcecode:: http

   **Example response**:

   .. sourcecode:: http

   OK
"""

from django.shortcuts import get_object_or_404
from rest_framework.generics import CreateAPIView, DestroyAPIView
from rest_framework.response import Response
from rest_framework import serializers, status

from saas.models import CartItem, Plan
from saas.mixins import CartMixin

#pylint: disable=no-init,old-style-class


class PlanRelatedField(serializers.RelatedField):

    def __init__(self, **kwargs):
        super(PlanRelatedField, self).__init__(
            queryset=Plan.objects.all(), **kwargs)

    # Django REST Framework 3.0
    def to_representation(self, obj):
        return obj.slug

    def to_internal_value(self, data):
        return get_object_or_404(Plan, slug=data)


class CartItemSerializer(serializers.ModelSerializer):

    plan = PlanRelatedField(read_only=False, required=True)

    class Meta:
        model = CartItem
        fields = ('plan', 'nb_periods', 'first_name', 'last_name', 'email')


class CartItemAPIView(CartMixin, CreateAPIView):
    """
    Add a plan into the cart of the request user.

    **Example request**:

    .. sourcecode:: http

        POST /api/cart/

        {
            "plan": "open-space",
            "nb_periods": 1,
            "first_name": "",
            "last_name": "",
            "email": ""
        }

    **Example response**:

    .. sourcecode:: http

        {
            "plan": "open-space",
            "nb_periods": 1,
            "first_name": "",
            "last_name": "",
            "email": ""
        }
    """
    #pylint: disable=no-member

    model = CartItem
    serializer_class = CartItemSerializer

    # XXX This was a workaround until we figure what is wrong with proxy
    # and csrf, unfortunately it prevents authenticated users to add into
    # their db cart, instead put their choices into the unauth session.
    # authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.DATA)
        if serializer.is_valid():
            cart_item, created = self.insert_item(request, **serializer.data)
            # insert_item will either return a dict or a CartItem instance
            # (which cannot be directly serialized).
            if isinstance(cart_item, CartItem):
                cart_item = serializer.to_representation(cart_item)
            if created:
                headers = self.get_success_headers(cart_item)
                return Response(cart_item, status=status.HTTP_201_CREATED,
                    headers=headers)
            else:
                headers = self.get_success_headers(cart_item)
                return Response(cart_item, status=status.HTTP_200_OK,
                    headers=headers)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CartItemDestroyAPIView(DestroyAPIView):
    """
    Remove a ``Plan`` from the subscription cart of the request user.
    """

    model = CartItem

    @staticmethod
    def destroy_in_session(request, *args, **kwargs):
        #pylint: disable=unused-argument
        cart_items = []
        if request.session.has_key('cart_items'):
            cart_items = request.session['cart_items']
        candidate = kwargs.get('plan')
        serialized_cart_items = []
        found = False
        for item in cart_items:
            if item['plan'] == candidate:
                found = True
                continue
            serialized_cart_items += [item]
        request.session['cart_items'] = serialized_cart_items
        return found

    def get_object(self):
        return get_object_or_404(CartItem,
            plan__slug=self.kwargs.get('plan'), user=self.request.user)

    def delete(self, request, *args, **kwargs):
        destroyed = self.destroy_in_session(request, *args, **kwargs)
        # We found the items in the session cart, nothing else to do.
        if not destroyed and self.request.user.is_authenticated():
            # If the user is authenticated, we delete the cart items
            # from the database.
            return self.destroy(request, *args, **kwargs)
        return Response(status=status.HTTP_204_NO_CONTENT)



