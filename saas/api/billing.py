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

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import CreateAPIView, DestroyAPIView, UpdateAPIView
from rest_framework.response import Response
from rest_framework import serializers

from saas.compat import datetime_or_now
from saas.models import CartItem, Plan, Subscription

#pylint: disable=no-init
#pylint: disable=old-style-class

class SubscriptionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Subscription


class SubscriptionMixin(object):

    model = Subscription
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        return Subscription.objects.filter(
            organization__slug=self.kwargs.get('organization'),
            plan__slug=self.kwargs.get('plan'))


class PlanRelatedField(serializers.RelatedField):

    def to_native(self, value):
        return value.slug

    def from_native(self, data):
        return get_object_or_404(Plan, slug=data)


class CartItemSerializer(serializers.ModelSerializer):

    plan = PlanRelatedField(read_only=False, required=True)

    class Meta:
        model = CartItem
        fields = ('plan',)


class CartItemAPIView(CreateAPIView):

    model = CartItem
    serializer_class = CartItemSerializer

    def create_in_session(self, request):
        serializer = self.get_serializer(data=request.DATA, files=request.FILES)
        if serializer.is_valid():
            cart_items = []
            if request.session.has_key('cart_items'):
                cart_items = request.session['cart_items']
            found = False
            candidate = serializer.data['plan']
            for item in cart_items:
                if item['plan'] == candidate:
                    found = True
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
        serializer = self.get_serializer(data=request.DATA, files=request.FILES)
        if serializer.is_valid():
            self.pre_save(serializer.object)
            try:
                self.object = self.model.objects.get(
                    user=self.request.user, plan__slug=serializer.data['plan'])
                self.post_save(self.object, created=False)
                headers = self.get_success_headers(serializer.data)
                return Response(serializer.data, status=status.HTTP_200_OK,
                    headers=headers)
            except self.model.DoesNotExist:
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


class UnsubscribeAPIView(SubscriptionMixin, UpdateAPIView):
    """
    Unsubscribe an organization to a plan.
    """

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.ends_at = datetime_or_now()
        self.object.save()
        serializer = self.get_serializer(self.object)
        return Response(serializer.data) #pylint: disable=no-member


