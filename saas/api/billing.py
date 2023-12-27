# Copyright (c) 2023, DjaoDjin inc.
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
APIs for cart and checkout functionality.
"""
from __future__ import unicode_literals

import csv, logging

from django.contrib import messages
from rest_framework import generics
from rest_framework.mixins import CreateModelMixin
from rest_framework import response as http
from rest_framework import status

from ..backends import ProcessorError
from ..compat import gettext_lazy as _, is_authenticated, StringIO
from ..docs import extend_schema, OpenApiResponse
from ..filters import DateRangeFilter, OrderingFilter, SearchFilter
from ..mixins import (BalanceAndCartMixin, CartMixin, InvoicablesMixin,
                      UserMixin)
from ..models import CartItem, get_broker
from ..utils import datetime_or_now, get_user_serializer
from .serializers import (CartItemSerializer, CartItemCreateSerializer,
    CartItemUploadSerializer, ChargeSerializer, CheckoutSerializer,
    OrganizationCartSerializer, RedeemCouponSerializer,
    ValidationErrorSerializer, CartItemUpdateSerializer,
    UserCartItemCreateSerializer, QueryParamCartItemSerializer)


LOGGER = logging.getLogger(__name__)


class CartItemAPIView(CartMixin, generics.CreateAPIView):
    """
    Adds an item to the user cart

    Adds a plan into the cart of the user identified through the HTTP request.

    The cart can later be checked out and paid by a billing profile, either
    through the `HTML checkout page </docs/guides/themes/#workflow_billing_cart>`_
    or `API end point </docs/api/#createCheckout>`_.

    This end point is typically used when a user is presented with a list
    of add-ons that she can subscribes to in one checkout screen. The end-point
    works in both cases, authenticated or anonymous users. For authenticated
    users, the cart is stored in the database as ``CartItem`` objects.
    For anonymous users, the cart is stored in an HTTP Cookie.

    The end-point accepts a single item or a list of items.

    ``option`` is optional. When it is not specified, subsquent checkout
    screens will provide choices to pay multiple periods in advance.

    When additional ``full_name`` and ``sync_on`` are specified,
    payment can be made by one billing profile for another profile
    to be subscribed (see :ref:`GroupBuy orders <group_buy>`).

    **Tags**: billing, visitor, cartmodel

    **Examples**

    .. code-block:: http

        POST /api/cart HTTP/1.1

    .. code-block:: json

        {
            "plan": "premium",
            "option": 1
        }

    responds

    .. code-block:: json

        {
            "plan": {
              "slug": "premium",
              "title": "Premium"
            },
            "option": 1,
            "user": {
              "username": "xia",
              "slug": "xia",
              "full_name": "Xia Lee",
              "email": "xia@localhost.localdomain"
            }
        }

    """
    #pylint: disable=no-member

    model = CartItem
    serializer_class = CartItemCreateSerializer

    # XXX This was a workaround until we figure what is wrong with proxy
    # and csrf, unfortunately it prevents authenticated users to add into
    # their db cart, instead put their choices into the unauth session.
    # authentication_classes = []
    @extend_schema(responses={
      200: OpenApiResponse(CartItemSerializer),
      201: OpenApiResponse(CartItemSerializer)})
    def post(self, request, *args, **kwargs):
        items = None
        if isinstance(request.data, dict):
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                items = [serializer.validated_data]
        else:
            serializer_list = self.get_serializer(data=request.data, many=True)
            if serializer_list.is_valid(raise_exception=True):
                items = serializer_list.validated_data

        cart_items = []
        at_time = datetime_or_now()
        status_code = status.HTTP_200_OK
        serializer = CartItemSerializer()
        for item in items:
            cart_item, created = self.insert_item(
                request, at_time=at_time, **item)
            if created:
                status_code = status.HTTP_201_CREATED
            # insert_item will either return a dict or a CartItem instance
            # (which cannot be directly serialized).
            if isinstance(cart_item, CartItem):
                cart_item = serializer.to_representation(cart_item)
            cart_items += [cart_item]
        if len(items) > 1:
            headers = self.get_success_headers(cart_items)
            return http.Response(cart_items, status=status_code, headers=headers)
        headers = self.get_success_headers(cart_items[0])
        return http.Response(cart_items[0], status=status_code, headers=headers)

    @staticmethod
    def destroy_in_session(request, plan=None, email=None):
        cart_items = request.session.get('cart_items', [])
        serialized_cart_items = []
        is_deleted = False
        for item in cart_items:
            if plan and item['plan'] == plan:
                is_deleted = True
                continue
            if email and item['email'] == email:
                is_deleted = True
                continue
            serialized_cart_items += [item]
        if is_deleted:
            request.session['cart_items'] = serialized_cart_items
        return is_deleted

    @staticmethod
    def destroy_in_db(request, plan=None, email=None):
        kwargs = {}
        if plan:
            kwargs.update({'plan__slug': plan})
        if email:
            kwargs.update({'email': email})
        CartItem.objects.get_cart(request.user, **kwargs).delete()

    @extend_schema(parameters=[QueryParamCartItemSerializer])
    def delete(self, request, *args, **kwargs):
        """
        Removes an item from the user cart

        Removes an item from the ``request.user`` cart.

        **Tags**: billing, visitor, cartmodel

        **Examples**

        .. code-block:: http

            DELETE /api/cart?plan=premium HTTP/1.1
        """
        #pylint:disable=unused-argument
        query_serializer = QueryParamCartItemSerializer(
            data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        plan = query_serializer.validated_data.get('plan', None)
        email = query_serializer.validated_data.get('email', None)

        self.destroy_in_session(request, plan=plan, email=email)
        if is_authenticated(request):
            # If the user is authenticated, we delete the cart items
            # from the database.
            self.destroy_in_db(request, plan=plan, email=email)
        return http.Response(status=status.HTTP_204_NO_CONTENT)


class CartItemUploadAPIView(CartMixin, generics.GenericAPIView):
    """
    Uploads multiple items into a user cart

    Add a ``Plan`` into the subscription cart of multiple users as per the
    content of an uploaded file.

    This works bulk fashion of :ref:`/cart/ endpoint<api_cart>`. The
    uploaded file must be a CSV containing the fields ``first_name``,
    ``last_name`` and email. The CSV file must not contain a header
    line, only data.

    **Tags**: billing, cartmodel

    **Examples**

    Content of ``names.csv``:

    .. code-block:: csv

        Joe,Smith,joesmith@example.com
        Marie,Johnson,mariejohnson@example.com

    .. code-block:: http

        POST /api/cart/basic/upload HTTP/1.1

        Content-Disposition: form-data; name="file"; filename="names.csv"
        Content-Type: text/csv

    responds

    .. code-block:: json

        {
            "created": [
                {
                    "plan": {
                      "slug": "basic",
                      "title": "Basic"
                    },
                    "user": {
                        "username": "joe",
                        "slug": "joe",
                        "full_name": "Joe Smith",
                        "email": "joesmith@example.com"
                    }
                },
                {
                    "plan": {
                      "slug": "basic",
                      "title": "Basic"
                    },
                    "user": {
                        "username": "mariejohnson",
                        "slug": "mariejohnson",
                        "full_name": "Marie Johnson",
                        "email": "mariejohnson@example.com"
                    }
                }
            ],
            "updated": [],
            "failed": []
        }
    """
    serializer_class = CartItemUploadSerializer

    def post(self, request, *args, **kwargs):
        #pylint:disable=unused-argument,too-many-locals
        plan = kwargs.get('plan')
        response = {'created': [],
                    'updated': [],
                    'failed': []}
        uploaded = request.FILES.get('file')
        filed = csv.reader(StringIO(uploaded.read().decode(
            'utf-8', 'ignore')) if uploaded else StringIO())

        at_time = datetime_or_now()
        status_code = status.HTTP_200_OK
        resp_serializer = CartItemSerializer()
        for row in filed:
            try:
                if len(row) == 2:
                    full_name, email = row
                elif len(row) == 3:
                    first_name, last_name, email = row
                    full_name = '%s %s' % (first_name, last_name)
                else:
                    raise csv.Error()
            except csv.Error:
                response['failed'].append({'data': {'raw': row},
                                           'error': 'Unable to parse row'})
            else:
                serializer = CartItemCreateSerializer(
                    data={'plan': plan,
                          'full_name': full_name,
                          'sync_on': email,
                          'email': email})
                if serializer.is_valid():
                    # similar code as `CartItemAPIView.post`
                    cart_item, created = self.insert_item(
                        request, at_time=at_time, **serializer.data)
                    if isinstance(cart_item, CartItem):
                        cart_item = resp_serializer.to_representation(cart_item)
                    if created:
                        status_code = status.HTTP_201_CREATED
                        response['created'].append(cart_item)
                    else:
                        response['updated'].append(cart_item)
                else:
                    response['failed'].append({'data': serializer.data,
                                               'error': serializer.errors})

        return http.Response(response, status=status_code)


class CouponRedeemAPIView(generics.GenericAPIView):
    """
    Redeems a discount code

    Redeems a ``Coupon`` and applies the discount to the eligible items
    in the cart.

    **Tags**: billing, visitor, cartmodel

    **Examples**

    .. code-block:: http

         POST /api/cart/redeem HTTP/1.1

    .. code-block:: json

        {
            "code": "LABORDAY"
        }

    responds

    .. code-block:: json

        {
            "detail": "Coupon 'LABORDAY' was successfully applied."
        }
    """
    serializer_class = RedeemCouponSerializer

    # XXX This is not a ValidationErrorSerializer but we return a message.
    # XXX Should many return the updated cart but we are dealing with users,
    # not organizations here.
    @extend_schema(responses={
        200: OpenApiResponse(ValidationErrorSerializer)})
    def post(self, request, *args, **kwargs): #pylint: disable=unused-argument
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            coupon_code = serializer.data['code']
            if CartItem.objects.redeem(request.user, coupon_code):
                details = {'detail': (
                    _("Coupon '%(code)s' was successfully applied.") % {
                        'code': coupon_code})}
                headers = {}
                # XXX Django 1.7: 500 error, argument must be an HttpRequest
                # object, not 'Request'. Not an issue with Django 1.6.2
                # Since we rely on the message to appear after reload of
                # the cart page in the casperjs tests, we can't get rid
                # of this statement just yet.
                #pylint: disable=protected-access
                messages.success(request._request, details['detail'])
                return http.Response(details, status=status.HTTP_200_OK,
                                headers=headers)
            details = {'detail': (
                _("No items can be discounted using this coupon: %(code)s.") % {
                'code': coupon_code})}
            return http.Response(details, status=status.HTTP_400_BAD_REQUEST)
        return http.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CheckoutAPIView(InvoicablesMixin, BalanceAndCartMixin,
                      CreateModelMixin, generics.RetrieveAPIView):
    """
    Retrieves a cart for checkout

    Get a list indexed by plans of items that will be charged
    (`lines`) and options that could be charged instead.

    In many subscription businesses, it is possible to buy multiple
    period in advance at a discount. The options reflects that.

    The API is typically used within an HTML
    `checkout page </docs/guides/themes/#workflow_billing_cart>`_
    as present in the default theme.

    **Tags**: billing, subscriber, cartmodel

    **Examples**

    .. code-block:: http

        GET /api/billing/xia/checkout HTTP/1.1

    responds

    .. code-block:: json

        {
          "results": [
          {
            "subscription": {
              "created_at":"2016-06-21T23:24:09.242925Z",
              "ends_at":"2016-10-21T23:24:09.229768Z",
              "description":null,
              "profile": {
                  "slug": "xia",
                  "printable_name": "Xia Lee",
                  "picture": null,
                  "type": "personal",
                  "credentials": true
              },
              "plan": {
                  "slug": "basic",
                  "title": "Basic"
              },
              "auto_renew":true
            },
            "lines": [
            {
              "created_at":"2016-06-21T23:42:13.863739Z",
              "description":"Subscription to basic until 2016/11/21 (1 month)",
              "amount":"$20.00",
              "is_debit":false,
              "orig_account":"Receivable",
              "orig_profile": {
                  "slug": "cowork",
                  "printable_name": "Coworking Space",
                  "picture": null,
                  "type": "organization",
                  "credentials": false
              },
              "orig_amount":2000,
              "orig_unit":"usd",
              "dest_account":"Payable",
              "dest_profile": {
                  "slug": "xia",
                  "printable_name": "Xia Lee",
                  "picture": null,
                  "type": "personal",
                  "credentials": true
              },
              "dest_amount":2000,
              "dest_unit":"usd"
            }],
            "options":[]
          }]
        }
    """
    serializer_class = OrganizationCartSerializer

    def get_serializer_class(self):
        if self.request.method.lower() in ('post',):
            return CheckoutSerializer
        return super(CheckoutAPIView, self).get_serializer_class()

    @extend_schema(responses={
        201: OpenApiResponse(ChargeSerializer)})
    def post(self, request, *args, **kwargs):
        """
        Checkouts a cart

        Places an order for the subscription items in the cart and creates
        a ``Charge`` on the billing profile payment method.

        If the charge fails a balance is due, to be collected later.

        The cart is manipulated through various API endpoints:

        - `Redeems a discount code </docs/api/#createCouponRedeem>`_ applies \
a coupon code for a potential discount, and
        - `Adds an item to the request user cart </docs/api/#createCartItem>`_,\
 `Removes an item from the request user cart </docs/api/#destroyCartItem>`_\
 to update a cart.

        The API is typically used within an HTML
        `checkout page </docs/guides/themes/#workflow_billing_cart>`_
        as present in the default theme.

        **Tags**: billing, subscriber, cartmodel

        **Examples**

        .. code-block:: http

            POST /api/billing/xia/checkout HTTP/1.1

        .. code-block:: json

            {
                "remember_card": true,
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

    def get(self, request, *args, **kwargs):
        provider = self.invoicables_provider
        resp_data = {
            'processor':
            provider.processor_backend.get_payment_context(# checkout
                self.organization,
                amount=self.invoicables_lines_price.amount,
                unit=self.invoicables_lines_price.unit,
                broker_fee_amount=self.invoicables_broker_fee_amount,
                provider=provider, broker=get_broker()),
            'results': self.get_queryset()
        }
        serializer = self.get_serializer(resp_data)
        return http.Response(serializer.data)

    def create(self, request, *args, **kwargs):#pylint:disable=unused-argument
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        queryset = self.get_queryset()
        items_options = data.get('items')
        if items_options:
            for index, item in enumerate(items_options):
                opt_index = item['option'] - 1
                if index >= len(queryset):
                    continue
                if (opt_index < 0 or
                    opt_index >= len(queryset[index]['options'])):
                    continue
                selected = queryset[index]['options'][opt_index]
                queryset[index]['lines'].append(selected)
        self.organization.update_address_if_empty(country=data.get('country'),
            region=data.get('region'), locality=data.get('locality'),
            street_address=data.get('street_address'),
            postal_code=data.get('postal_code'))

        try:
            charge = self.organization.checkout(
                queryset, self.request.user,
                token=data.get('processor_token'),
                remember_card=data.get('remember_card', False))
            if charge and charge.invoiced_total.amount > 0:
                result = ChargeSerializer(charge)
                return http.Response(result.data, status=status.HTTP_200_OK)
        except ProcessorError as err:
            return http.Response({
                'detail': str(err)}, status=status.HTTP_400_BAD_REQUEST)
        return http.Response({}, status=status.HTTP_200_OK)


class ActiveCartItemListCreateView(generics.ListCreateAPIView):
    """
    Lists active cart items

    Returns a list of {{PAGE_SIZE}} cart items that haven't been checked out
    yet.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    **Tags**: billing, broker, cart

    **Examples**

    .. code-block:: http

        GET /api/billing/cartitems HTTP/1.1

    responds

    .. code-block:: json

        {
          "count": 1,
          "next": null,
          "previous": null,
          "results": [{
            "created_at": "2023-10-11T21:20:06.444545-05:00",
            "user": {
              "username": "xia",
              "slug": "xia",
              "email": "xia@example.com",
              "full_name": "Xia Lee",
              "created_at": "2023-09-06T21:49:28.003319-05:00",
              "last_login": "2023-10-11T03:31:10.138177-05:00"
            },
            "plan": {
              "slug": "basic",
              "title": "Basic"
            },
            "option": 0,
            "use": null,
            "quantity": 1,
            "sync_on": null,
            "full_name": "Xia Lee",
            "email": "xia@example.com",
            "detail": null
          }]
        }
    """
    search_fields = (
        'user__username',
        'user__first_name',
        'user__last_name',
        'user__email',
    )
    ordering_fields = (
        ('user__username', 'username'),
        ('created_at', 'created_at')
    )
    ordering = ('created_at',)

    filter_backends = (DateRangeFilter, SearchFilter, OrderingFilter)
    queryset = CartItem.objects.filter(recorded=False).select_related(
        'user', 'plan')
    serializer_class = CartItemSerializer

    def get_serializer_class(self):
        if self.request.method.lower() in ['post']:
            return UserCartItemCreateSerializer
        return CartItemSerializer


    @extend_schema(responses={
        201: OpenApiResponse(CartItemSerializer)})
    def post(self, request, *args, **kwargs):
        """
        Creates a cart item

        This endpoint lets broker to add items into a user cart.

        **Tags**: billing, broker, cart

        **Examples**

        .. code-block:: http

            POST /api/billing/cartitems HTTP/1.1

        .. code-block:: json

            {
                "user": "xia",
                "plan": "basic"
            }

        responds

        .. code-block:: json

            {
              "user": {
                "username": "xia",
                "slug": "xia",
                "email": "xia@example.com",
                "full_name": "Xia Lee",
                "created_at": "2023-09-06T21:49:28.003319-05:00",
                "last_login": "2023-10-11T03:31:10.138177-05:00"
              },
              "plan": {
                "slug": "basic",
                "title": "Basic"
              },
              "created_at": "2023-10-12T05:47:17.421103-05:00",
              "option": 3,
              "use": null,
              "quantity": 50,
              "sync_on": "",
              "full_name": "Xia Lee",
              "email": "xia@example.com",
              "detail": "Cart item created"
            }
        """
        response = super(ActiveCartItemListCreateView, self).create(
            request, *args, **kwargs)
        if response.status_code == status.HTTP_201_CREATED:
            response.data['detail'] = _('Cart item created')

        return http.Response(response.data, status=status.HTTP_201_CREATED,
                             headers=response.headers)


class ActiveCartItemRetrieveUpdateDestroyView(
        generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieves a cart item

    Returns a single cart item based on its primary key.

    This API endpoint is intended for broker to analyze and modify
    active cart items as necessary when responding to support requests.

    **Tags**: billing, broker, cart

    **Examples**

    .. code-block:: http

        GET /api/billing/cartitems/{cartitem_id} HTTP/1.1

    responds

    .. code-block:: json

        {
          "user": {
            "username": "xia",
            "slug": "xia",
            "email": "xia@example.com",
            "full_name": "Xia Lee",
            "created_at": "2023-09-06T21:49:28.003319-05:00",
            "last_login": "2023-10-11T03:31:10.138177-05:00"
          },
          "plan": {
            "slug": "basic",
            "title": "Basic"
          },
          "created_at": "2023-10-11T23:22:54.407880-05:00",
          "option": 3,
          "use": null,
          "quantity": 50,
          "sync_on": null,
          "full_name": "Xia Lee",
          "email": "xia@example.com"
        }
    """
    lookup_field = "id"
    lookup_url_kwarg = "cartitem_id"
    queryset = CartItem.objects.filter(recorded=False).select_related(
        'user', 'plan')

    def get_serializer_class(self):
        if self.request.method.lower() in ['put', 'patch']:
            return CartItemUpdateSerializer
        return CartItemSerializer


    def delete(self, request, *args, **kwargs):
        """
        Deletes a cart item

        Deletes a single cart item based on its primary key.

        This API endpoint is intended for broker to analyze and modify
        active cart items as necessary when responding to support requests.

        **Tags**: billing, broker, cart

        **Examples**

        .. code-block:: http

            DELETE /api/billing/cartitems/{cartitem_id} HTTP/1.1
        """
        return self.destroy(request, *args, **kwargs)


    @extend_schema(responses={
        200: OpenApiResponse(CartItemUpdateSerializer)})
    def put(self, request, *args, **kwargs):
        """
        Updates a cart item

        Updates a single cart item based on its primary key.

        This API endpoint is intended for broker to analyze and modify
        active cart items as necessary when responding to support requests.

        **Tags**: billing, broker, cart

        **Examples**

        .. code-block:: http

            PUT /api/billing/cartitems/{cartitem_id} HTTP/1.1

        .. code-block:: json

            {
              "option": 2,
              "quantity": 25
            }

        responds

        .. code-block:: json

            {
                "created_at": "2023-10-12T02:04:49.151044-05:00",
                "user": {
                    "slug": "xia",
                    "email": "xia@example.com",
                    "full_name": "Xia Lee",
                    "created_at": "2023-09-06T21:58:07.969908-05:00",
                    "last_login": "2023-10-12T01:49:13.092566-05:00"
                },
                "plan": {
                    "slug": "basic",
                    "title": "Basic"
                },
                "option": 2,
                "use": null,
                "quantity": 25,
                "sync_on": "",
                "full_name": "",
                "email": "",
                "detail": "Cart item updated"
            }
        """
        response = self.update(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            response.data['detail'] = _('Cart item updated')

        return http.Response(response.data, status=response.status_code)


class UserCartItemListView(UserMixin, generics.ListAPIView):
    """
    Lists a user active cart items

    Returns a list of {{PAGE_SIZE}} cart items that a specified user hasn't
    checked out yet.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    **Tags**: billing, broker, cart

    **Examples**

    .. code-block:: http

        GET /api/billing/cartitems/user/xia HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2023-10-11T23:49:59.485511-05:00",
                    "user": {
                        "username": "xia",
                        "slug": "xia",
                        "email": "xia@example.com",
                        "full_name": "Xia Lee",
                        "created_at": "2023-09-06T21:49:28.003319-05:00",
                        "last_login": "2023-10-11T03:31:10.138177-05:00"
                    },
                    "plan": {
                        "slug": "basic",
                        "title": "Basic"
                    },
                    "option": 0,
                    "use": null,
                    "quantity": 2,
                    "sync_on": null,
                    "full_name": "",
                    "email": null,
                    "id": 137
                }]
            }
        """
    search_fields = (
        'user__username',
        'user__first_name',
        'user__last_name',
        'user__email',
    )
    ordering_fields = (
        ('user__username', 'username'),
        ('created_at', 'created_at')
    )
    ordering = ('created_at',)

    filter_backends = (DateRangeFilter, SearchFilter, OrderingFilter)
    queryset = CartItem.objects.filter(recorded=False).select_related(
        'user', 'plan')
    serializer_class = CartItemSerializer

    def get_serializer(self, *args, **kwargs):
        serializer = super(UserCartItemListView, self).get_serializer(
            *args, **kwargs)
        # Check if the serializer has a 'child' attribute (indicating it's a
        # ListSerializer)
        if hasattr(serializer, 'child'):
            # Accessing child serializer because ListSerializer is the
            # parent serializer for querysets.
            # https://www.django-rest-framework.org/api-guide/serializers/#listserializer
            # The child serializer is then responsible for each individual
            # object. Another way to do it would be to loop through each item
            # in the queryset and remove "user" from the representation,
            # but this might be more efficient.
            child_serializer = serializer.child
            original_to_representation = child_serializer.to_representation

            def _to_representation(instance):
                # Adding the "id" field
                representation = original_to_representation(instance)
                representation['id'] = instance.id
                # Removing the "user" field
                representation.pop('user', None)
                return representation

            child_serializer.to_representation = _to_representation
        return serializer

    def get_queryset(self):
        user = self.user if self.user is not None else self.request.user
        # The queryset = (...) returns a queryset meaning
        # ListSerializer is automatically used
        queryset = self.queryset.filter(user=user)
        return queryset

    def list(self, request, *args, **kwargs):
        response = super(UserCartItemListView, self).list(
            request, *args, **kwargs)
        user = self.user if self.user is not None else self.request.user
        user_data = get_user_serializer()(user).data
        # Adding user_data here otherwise it gets repeated for each cartitem
        # Adding all items except the "results" in order to show the
        # User field before the "results."
        data = {k: response.data[k] for k in list(response.data.keys())[:-1]}
        data['user'] = user_data
        data['results'] = response.data['results']

        return http.Response(data)
