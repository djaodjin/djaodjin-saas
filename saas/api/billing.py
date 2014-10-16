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

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import CreateAPIView, DestroyAPIView
from rest_framework.response import Response
from rest_framework import serializers

from saas.models import CartItem, Plan

#pylint: disable=no-init,old-style-class


class PlanRelatedField(serializers.RelatedField):

    def to_native(self, value):
        return value.slug

    def from_native(self, data):
        return get_object_or_404(Plan, slug=data)


class CartItemSerializer(serializers.ModelSerializer):

    plan = PlanRelatedField(read_only=False, required=True)

    class Meta:
        model = CartItem
        fields = ('plan', 'nb_periods', 'first_name', 'last_name', 'email')


class CartItemAPIView(CreateAPIView):

    model = CartItem
    serializer_class = CartItemSerializer
    fields = ('plan', 'nb_periods', 'coupon',
        'first_name', 'last_name', 'email')

    # XXX This was a workaround until we figure what is wrong with proxy
    # and csrf, unfortunately it prevents authenticated users to add into
    # their db cart, instead put their choices into the unauth session.
    # authentication_classes = []

    def create_in_session(self, request):
        serializer = self.get_serializer(data=request.DATA, files=request.FILES)
        if serializer.is_valid():
            cart_items = []
            if request.session.has_key('cart_items'):
                cart_items = request.session['cart_items']
            found = False
            for item in cart_items:
                found = True
                # XXX all serialized fields match ...
                for field in self.fields:
                    if field in serializer.data and field in item:
                        found &= (serializer.data[field] == item[field])
                if found:
                    break
            if not found:
                cart_items += [serializer.data] # because unable to serialize
                                                # Models (serializer.object).
            request.session['cart_items'] = cart_items
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data,
                            status=status.HTTP_201_CREATED,
                            headers=headers)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def pre_save(self, obj):
        """
        Find the ``Cart`` this new item goes into.
        """
        # We would call the super.pre_save but it does weird things
        # that look like security risks (ex: trying to set the id or slug.)
        setattr(obj, 'user', self.request.user)

    def create_or_none(self, request):
        self.object = None
        if 'plan' in request.DATA:
            email = request.DATA.get('email', '')
            queryset = self.model.objects.filter(
                Q(email__isnull=True) | Q(email='') | Q(email=email),
                user=self.request.user,
                plan__slug=request.DATA['plan']).order_by('-email')
            if queryset.exists():
                self.object = queryset.first()
        serializer = self.get_serializer(
            instance=self.object, data=request.DATA, files=request.FILES)
        if serializer.is_valid():
            self.pre_save(serializer.object)
            if not self.object:
                queryset = self.model.objects.filter(
                    user=self.request.user,
                    plan__slug=request.DATA['plan'])
                if queryset.exists():
                    cart_item = queryset.get()
                    for field in self.fields:
                        if not getattr(serializer.object, field):
                            setattr(serializer.object, field,
                                getattr(cart_item, field))
            if serializer.object.email:
                # When adding seated subscriptions to the cart (i.e.
                # explicit email field) we must have a nb_periods,
                # XXX a constraint from the user interface.
                periods_queryset = queryset.exclude(nb_periods=0)
                if periods_queryset.exists():
                    setattr(serializer.object,
                        'nb_periods', periods_queryset.first().nb_periods)
                else:
                    return Response({'nb_periods':
                        ['Adding a seat and no period specified']},
                        status=status.HTTP_400_BAD_REQUEST)
            if self.object:
                self.object = serializer.save()
                self.post_save(self.object, created=False)
                headers = self.get_success_headers(serializer.data)
                return Response(serializer.data, status=status.HTTP_200_OK,
                    headers=headers)
            else:
                self.object = serializer.save(force_insert=True)
                self.post_save(self.object, created=True)
                headers = self.get_success_headers(serializer.data)
                return Response(serializer.data, status=status.HTTP_201_CREATED,
                    headers=headers)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, *args, **kwargs):
        if self.request.user.is_authenticated():
            # If the user is authenticated, we just create the cart items
            # into the database.
            return self.create_or_none(request, *args, **kwargs)
        else:
            # We have an anonymous user so let's play some tricks with
            # the session data.
            return self.create_in_session(request)


class CartItemDestroyAPIView(DestroyAPIView):
    """
    Remove a ``Plan`` into the subscription cart of a ``User``.
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

    def get_object(self, queryset=None):
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



