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
from __future__ import unicode_literals

from collections import OrderedDict

from django.db.models import Q
from rest_framework import generics, status, response as http
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination

from .serializers import (CartItemCreateSerializer,
    CreateOfflineTransactionSerializer, OfflineTransactionSerializer,
    TransactionSerializer)
from ..compat import gettext_lazy as _
from ..decorators import _valid_manager
from ..docs import extend_schema, OpenApiResponse
from ..filters import DateRangeFilter, OrderingFilter, SearchFilter
from ..mixins import OrganizationMixin, ProviderMixin, DateRangeContextMixin
from ..models import (get_broker, record_use_charge, sum_orig_amount,
    Subscription, Transaction, Plan)
from ..backends import ProcessorError
from ..pagination import (BalancePagination, StatementBalancePagination,
    TotalPagination)
from ..utils import datetime_or_now, get_organization_model


class IncludesSyncErrorPagination(PageNumberPagination):

    def paginate_queryset(self, queryset, request, view=None):
        #pylint:disable=attribute-defined-outside-init
        if view and hasattr(view, 'processor_error'):
            self.detail = view.processor_error
        return super(IncludesSyncErrorPagination, self).paginate_queryset(
            queryset, request, view=view)

    def get_paginated_response(self, data):
        paginated = [
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]
        if hasattr(self, 'detail'):
            paginated += [('detail', self.detail)]
        return http.Response(OrderedDict(paginated))


class TotalAnnotateMixin(object):

    def get_queryset(self):
        queryset = super(TotalAnnotateMixin, self).get_queryset()
        self.totals = sum_orig_amount(queryset)
        return queryset


class SmartTransactionListMixin(DateRangeContextMixin):
    """
    The queryset can be further filtered to a range of dates between
    ``start_at`` and ``ends_at``.

    The queryset can be further filtered by passing a ``q`` parameter.
    The value in ``q`` will be matched against:

      - description
      - dest_profile
      - dest_profile__full_name
      - orig_profile
      - orig_profile__full_name

    The result queryset can be ordered by passing an ``o`` (field name)
    and ``ot`` (asc or desc) parameter.
    The fields the queryset can be ordered by are:

      - descr
      - dest_amount
      - dest_organization__slug
      - dest_organization__full_name
      - dest_account
      - orig_organization__slug
      - orig_organization__full_name
      - orig_account
      - created_at
    """
    search_fields = (
        'description',
        'dest_profile',
        'dest_profile__full_name',
        'orig_profile',
        'orig_profile__full_name',
    )
    alternate_fields = {
        'description': 'descr',
        'dest_profile': 'dest_organization__slug',
        'dest_profile__full_name': 'dest_organization__full_name',
        'orig_profile': 'orig_organization__slug',
        'orig_profile__full_name': 'orig_organization__full_name',
    }
    ordering_fields = (
        ('descr', 'description'),
        ('dest_amount', 'amount'),
        ('dest_organization__slug', 'dest_profile'),
        ('dest_organization__full_name', 'dest_profile__full_name'),
        ('dest_account', 'dest_account'),
        ('orig_organization__slug', 'orig_profile'),
        ('orig_organization__full_name', 'orig_profile__full_name'),
        ('orig_account', 'orig_account'),
        ('created_at', 'created_at')
    )
    ordering = ('created_at',)


    filter_backends = (DateRangeFilter, SearchFilter, OrderingFilter)


class TransactionQuerysetMixin(object):

    def get_queryset(self):
        self.selector = self.request.GET.get('selector', None)
        if self.selector is not None:
            queryset = Transaction.objects.filter(
                Q(dest_account__icontains=self.selector)
                | Q(orig_account__icontains=self.selector))
        else:
            queryset = Transaction.objects.all()
        # `TransactionSerializer` will expand `orig_organization`
        # and `dest_organization` so we add `select_related` for the ORM
        # to generate expected SQL.
        queryset = queryset.select_related(
            'orig_organization').select_related('dest_organization')
        return queryset


class TransactionListAPIView(SmartTransactionListMixin,
                             TransactionQuerysetMixin, generics.ListAPIView):
    """
    Lists ledger transactions

    Returns a list of {{PAGE_SIZE}} transactions.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    **Tags**: billing, list, broker, transactionmodel

    **Examples**

    .. code-block:: http

        GET /api/billing/transactions?start_at=2015-07-05T07:00:00.000Z\
&o=date&ot=desc HTTP/1.1

    responds

    .. code-block:: json

        {
            "start_at": "2015-07-05T07:00:00.000Z",
            "ends_at": "2017-03-30T18:10:12.962859Z",
            "balance_amount": 11000,
            "balance_unit": "usd",
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2017-02-01T00:00:00Z",
                    "description": "Charge for 4 periods",
                    "amount": "($356.00)",
                    "is_debit": true,
                    "orig_account": "Liability",
                    "orig_profile": {
                        "slug": "xia",
                        "printable_name": "Xia",
                        "picture": null,
                        "type": "personal",
                        "credentials": true
                    },
                    "orig_amount": 112120,
                    "orig_unit": "usd",
                    "dest_account": "Funds",
                    "dest_profile": {
                        "slug": "stripe",
                        "printable_name": "Stripe",
                        "picture": null,
                        "type": "organization",
                        "credentials": false
                    },
                    "dest_amount": 112120,
                    "dest_unit": "usd"
                }
            ]
        }
    """
    pagination_class = BalancePagination
    serializer_class = TransactionSerializer


class BillingsQuerysetMixin(OrganizationMixin):

    def get_queryset(self):
        """
        Get the list of transactions for this organization.
        """
        return Transaction.objects.by_customer(self.organization)


class BillingsAPIView(SmartTransactionListMixin,
                      BillingsQuerysetMixin, generics.ListAPIView):
    """
    Lists subscriber transactions

    Returns a list of {{PAGE_SIZE}} transactions associated
    to a billing profile while the profile acts as a subscriber.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    The API is typically used within an HTML
    `billing history page </docs/guides/themes/#dashboard_billing_history>`_
    as present in the default theme.

    **Tags**: billing, list, subscriber, transactionmodel

    **Examples**

    .. code-block:: http

         GET /api/billing/xia/history?start_at=2015-07-05T07:00:00.000Z\
 HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "start_at": "2015-01-01T00:00:00Z",
            "ends_at": "2016-01-01T00:00:00Z",
            "balance_unit": "usd",
            "balance_amount": 11000,
            "balance_unit": "usd",
            "results": [
                {
                    "created_at": "2015-08-01T00:00:00Z",
                    "description": "Charge for 4 periods",
                    "amount": "($356.00)",
                    "is_debit": true,
                    "orig_account": "Liability",
                    "orig_profile": {
                        "slug": "xia",
                        "printable_name": "Xia",
                        "picture": null,
                        "type": "personal",
                        "credentials": true
                    },
                    "orig_amount": 112120,
                    "orig_unit": "usd",
                    "dest_account": "Funds",
                    "dest_profile": {
                        "slug": "stripe",
                        "printable_name": "Stripe",
                        "picture": null,
                        "type": "organization",
                        "credentials": false
                    },
                    "dest_amount": 112120,
                    "dest_unit": "usd"
                }
            ]
        }
    """
    serializer_class = TransactionSerializer
    pagination_class = StatementBalancePagination


class ReceivablesQuerysetMixin(ProviderMixin):

    def get_queryset(self):
        """
        Get the list of transactions for this organization.
        """
        queryset = self.provider.receivables().filter(orig_amount__gt=0)
        # `TransactionSerializer` will expand `orig_organization`
        # and `dest_organization` so we add `select_related` for the ORM
        # to generate expected SQL.
        queryset = queryset.select_related(
            'orig_organization').select_related('dest_organization')
        return queryset


class ReceivablesListAPIView(TotalAnnotateMixin, SmartTransactionListMixin,
                             ReceivablesQuerysetMixin, generics.ListAPIView):
    """
    Lists provider receivables

    Returns a list of {{PAGE_SIZE}} transactions marked as receivables
    associated to a billing profile while the profile acts as a provider.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    This API endpoint is typically used to find all sales for a provider,
    whether it was paid or not.

    **Tags**: billing, list, provider, transactionmodel

    **Examples**

    .. code-block:: http

         GET /api/billing/cowork/receivables?start_at=2015-07-05T07:00:00.000Z\
 HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "balance_amount": "112120",
            "balance_unit": "usd",
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2015-08-01T00:00:00Z",
                    "description": "Charge <a href='/billing/cowork/receipt/\
1123'>1123</a> distribution for demo562-premium",
                    "amount": "112120",
                    "is_debit": false,
                    "orig_account": "Funds",
                    "orig_profile": {
                        "slug": "stripe",
                        "printable_name": "Stripe",
                        "picture": null,
                        "type": "organization",
                        "credentials": false
                    },
                    "orig_amount": 112120,
                    "orig_unit": "usd",
                    "dest_account": "Funds",
                    "dest_profile": {
                        "slug": "cowork",
                        "printable_name": "Coworking Space",
                        "picture": null,
                        "type": "organization",
                        "credentials": false
                    },
                    "dest_amount": 112120,
                    "dest_unit": "usd"
                }
            ]
        }
    """
    serializer_class = TransactionSerializer
    pagination_class = TotalPagination


class TransferQuerysetMixin(ProviderMixin):

    def get_queryset(self):
        """
        Get the list of transactions for this organization.
        """
        try:
            reconcile = not bool(self.request.GET.get('force', False))
            return self.organization.get_transfers(reconcile=reconcile)
        except ProcessorError as err:
            self.processor_error = _("The latest transfers might"\
                " not be shown because there was an error with the backend"\
                " processor (ie. %(err)s).") % {'err': str(err)}
            return Transaction.objects.by_organization(self.organization)


class TransferListAPIView(SmartTransactionListMixin, TransferQuerysetMixin,
                          generics.ListAPIView):
    """
    Lists provider payouts

    Returns a list of {{PAGE_SIZE}} transactions associated
    to a billing profile while the profile acts as a provider.

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    The API is typically used within an HTML
    `funds page </docs/guides/themes/#dashboard_billing_transfers>`_
    as present in the default theme.

    **Tags**: billing, list, provider, transactionmodel

    **Examples**

    .. code-block:: http

         GET /api/billing/cowork/transfers?start_at=2015-07-05T07:00:00.000Z\
 HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2015-08-01T00:00:00Z",
                    "description": "Charge <a href='/billing/cowork/receipt/\
1123'>1123</a> distribution for demo562-premium",
                    "amount": "$1121.20",
                    "is_debit": false,
                    "orig_account": "Funds",
                    "orig_profile": {
                        "slug": "stripe",
                        "printable_name": "Stripe",
                        "picture": null,
                        "type": "organization",
                        "credentials": false
                    },
                    "orig_amount": 112120,
                    "orig_unit": "usd",
                    "dest_account": "Funds",
                    "dest_profile": {
                        "slug": "cowork",
                        "printable_name": "Coworking Space",
                        "picture": null,
                        "type": "organization",
                        "credentials": false
                    },
                    "dest_amount": 112120,
                    "dest_unit": "usd"
                }
            ]
        }
    """
    serializer_class = TransactionSerializer
    pagination_class = IncludesSyncErrorPagination


class ImportTransactionsAPIView(ProviderMixin, generics.CreateAPIView):

    serializer_class = CreateOfflineTransactionSerializer

    @extend_schema(responses={
        201: OpenApiResponse(OfflineTransactionSerializer)})
    def post(self, request, *args, **kwargs):
        """
        Creates an offline transaction

        The primary purpose of this API call is for a provider to keep
        accurate metrics for the performance of the product sold, regardless
        of payment options (online or offline).

        **Tags**: billing, provider, transactionmodel

        **Examples**

        .. code-block:: http

             POST /api/billing/cowork/transfers/import HTTP/1.1

        .. code-block:: json

            {
               "created_at": "2020-05-30T00:00:00Z",
               "amount": "10.00",
               "descr": "Paid by check",
               "subscription": "xia:premium"
            }

        responds

        .. code-block:: json

            {
               "detail":"Transaction imported successfully.",
               "results":[
                 {
                   "created_at": "2020-05-30T00:00:00Z",
                   "description": "Paid by check (alice)",
                   "amount": "$10.00",
                   "is_debit": false,
                   "orig_account": "Receivable",
                   "orig_profile": {
                        "slug": "djaoapp",
                        "printable_name": "DjaoApp",
                        "picture": null,
                        "type": "organization",
                        "credentials": false
                   },
                   "orig_amount": 1000,
                   "orig_unit": "usd",
                   "dest_account": "Payable",
                   "dest_profile": {
                        "slug": "xia",
                        "printable_name": "Xia",
                        "picture": null,
                        "type": "personal",
                        "credentials": true
                   },
                   "dest_amount": 1000,
                   "dest_unit": "usd"
                 },
                 {
                   "created_at": "2020-05-30T00:00:00Z",
                   "description": "Paid by check (alice)",
                   "amount": "$10.00",
                   "is_debit": false,
                   "orig_account": "Liability",
                   "orig_profile": {
                        "slug": "xia",
                        "printable_name": "Xia",
                        "picture": null,
                        "type": "personal",
                        "credentials": true
                   },
                   "orig_amount": 1000,
                   "orig_unit": "usd",
                   "dest_account": "Funds",
                   "dest_profile": {
                        "slug": "djaoapp",
                        "printable_name": "DjaoApp",
                        "picture": null,
                        "type": "organization",
                        "credentials": false
                   },
                   "dest_amount": 1000,
                   "dest_unit": "usd"
                 },
                 {
                   "created_at": "2020-05-30T00:00:00Z",
                   "description": "Keep a balanced ledger",
                   "amount": "$10.00",
                   "is_debit": false,
                   "orig_account": "Payable",
                   "orig_profile": {
                        "slug": "xia",
                        "printable_name": "Xia",
                        "picture": null,
                        "type": "personal",
                        "credentials": true
                   },
                   "orig_amount": 1000,
                   "orig_unit": "usd",
                   "dest_account": "Liability",
                   "dest_profile": {
                        "slug": "xia",
                        "printable_name": "Xia",
                        "picture": null,
                        "type": "personal",
                        "credentials": true
                   },
                   "dest_amount": 1000,
                   "dest_unit": "usd"
                 },
                 {
                   "created_at": "2020-05-30T00:00:00Z",
                   "description": "Paid by check (alice)",
                   "amount": "$10.00",
                   "is_debit": false,
                   "orig_account": "Backlog",
                   "orig_profile": {
                        "slug": "djaoapp",
                        "printable_name": "DjaoApp",
                        "picture": null,
                        "type": "organization",
                        "credentials": false
                   },
                   "orig_amount": 1000,
                   "orig_unit": "usd",
                   "dest_account": "Receivable",
                   "dest_profile": {
                        "slug": "djaoapp",
                        "printable_name": "DjaoApp",
                        "picture": null,
                        "type": "organization",
                        "credentials": false
                   },
                   "dest_amount": 1000,
                   "dest_unit": "usd"
                 },
                 {
                   "created_at": "2020-05-30T00:00:00Z",
                 "description":"Paid by check (alice) - Keep a balanced ledger",
                   "amount":"$0.20",
                   "is_debit":false,
                   "orig_account":"Funds",
                   "orig_profile": {
                        "slug": "djaoapp",
                        "printable_name": "DjaoApp",
                        "picture": null,
                        "type": "organization",
                        "credentials": false
                   },
                   "orig_amount":20,
                   "orig_unit":"usd",
                   "dest_account":"Offline",
                   "dest_profile": {
                        "slug": "djaoapp",
                        "printable_name": "DjaoApp",
                        "picture": null,
                        "type": "organization",
                        "credentials": false
                   },
                   "dest_amount":20,
                   "dest_unit":"usd"
                 }
               ]
            }

        """
        return super(ImportTransactionsAPIView, self).post(
            request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        parts = serializer.validated_data['subscription'].split(
            Subscription.SEP)
        if len(parts) != 2:
            raise ValidationError({
                'detail': _("Invalid subscription/plan field format")})
        subscriber = parts[0]
        plan = parts[1]
        subscriber = get_organization_model().objects.filter(slug=subscriber).first()
        if subscriber is None:
            raise ValidationError({'detail': _("Invalid subscriber")})
        plan = Plan.objects.filter(
            slug=plan, organization=self.organization).first()
        if plan is None:
            raise ValidationError({'detail': _("Invalid plan")})
        subscription = Subscription.objects.active_for(
            organization=subscriber).filter(plan=plan).first()
        if subscription is None:
            raise ValidationError({
                'detail': _("Invalid combination of subscriber and plan,"\
" or the subscription is no longer active.")})
        transactions = Transaction.objects.offline_payment(
            subscription, serializer.validated_data['amount'],
            descr=serializer.validated_data['descr'], user=self.request.user,
            created_at=serializer.validated_data.get('created_at'))

        result_data = {
            'detail': _("Transaction imported successfully."),
            'results': TransactionSerializer(
                many=True).to_representation(transactions)
        }
        headers = self.get_success_headers(result_data)
        return http.Response(result_data,
            status=status.HTTP_201_CREATED, headers=headers)


class StatementBalanceQuerysetMixin(OrganizationMixin):

    def get_queryset(self):
        return self.organization.last_unpaid_orders()


class StatementBalanceAPIView(SmartTransactionListMixin,
                    StatementBalanceQuerysetMixin, generics.ListCreateAPIView):
    """
    Retrieves a customer balance

    Get the statement balance due for a billing profile.

    **Tags**: billing, subscriber, transactionmodel

    **Examples**

    .. code-block:: http

         GET  /api/billing/xia/balance HTTP/1.1

    responds

    .. code-block:: json

        {
            "balance_amount": "1200",
            "balance_unit": "usd",
            "start_at": "2023-01-01T00:00:00Z",
            "ends_at": "2023-06-01T23:42:13.863739Z",
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
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
                }]
        }
    """
    pagination_class = BalancePagination
    serializer_class = TransactionSerializer

    ordering = ('-created_at',)

    def get_serializer_class(self):
        if self.request.method.lower() in ('post',):
            return CartItemCreateSerializer
        return super(StatementBalanceAPIView, self).get_serializer_class()

    def get(self, request, *args, **kwargs):
        #pylint:disable=attribute-defined-outside-init
        self.balance_amount, self.balance_unit \
            = Transaction.objects.get_statement_balance(self.organization)
        return super(StatementBalanceAPIView, self).get(
            request, *args, **kwargs)

    @extend_schema(responses={
        201: OpenApiResponse(TransactionSerializer)})
    def post(self, request, *args, **kwargs):
        """
        Adds to the order balance

        This API endpoint can be used to add use charges to a subscriber
        invoice while charging the subscriber at a later date.

        **Tags**: billing, subscriber

        **Examples**

        .. code-block:: http

            POST /api/billing/xia/balance HTTP/1.1

        .. code-block:: json

            {
                "plan": "basic",
                "use": "requests"
            }

        responds

        .. code-block:: json

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
            }
        """
        return self.create(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.validated_data.get('plan')
        use_charge = serializer.validated_data.get('use')
        quantity = serializer.validated_data.get('quantity')
        if use_charge:
            subscription = Subscription.objects.valid_for(
                organization=self.organization, plan=plan,
                ends_at__gt=datetime_or_now()).first()
            order_executed_items = record_use_charge(
                subscription, use_charge, quantity=quantity)
            serializer = self.serializer_class(instance=order_executed_items[0])
            return http.Response(serializer.data, status=status.HTTP_201_CREATED)
        return http.Response({}, status=status.HTTP_200_OK)


    def delete(self, request, *args, **kwargs):
        """
        Cancels a balance due

        Cancel the balance due by profile. This will create
        a transaction for this balance cancellation. A provider manager can
        use this endpoint to cancel balance dues that is known impossible
        to be recovered (e.g. an external bank or credit card company
        act).

        **Tags**: billing, provider, transactionmodel

        **Examples**

        .. code-block:: http

             DELETE /api/billing/xia/balance HTTP/1.1
        """
        return self.destroy(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs): #pylint:disable=unused-argument
        if not _valid_manager(request, [get_broker()]):
            # XXX temporary workaround to provide GET balance API
            # to subscribers and providers.
            raise PermissionDenied()
        self.organization.create_cancel_transactions(user=request.user)
        return http.Response(status=status.HTTP_204_NO_CONTENT)
