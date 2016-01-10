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

"""
The two primary views to place an order are ``CartView`` and ``BalanceView``.
``CartView`` is used to implement the checkout and place a new order while
``BalanceView`` is used to pay an ``Organization`` balance due, either because
a charge wasn't sucessful and/or the provider implements a subscribe-pay-later
policy.

1. ``CartView`` for items in the cart, create new subscriptions
   or pay in advance.

2. ``BalanceView`` for subscriptions with balance dues
"""
#pylint:disable=too-many-lines

import copy, logging
from datetime import datetime
from decimal import Decimal

from django import http
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.views.generic import (DetailView, FormView, ListView, TemplateView,
    UpdateView)

from .. import settings
from ..api.transactions import (SmartTransactionListMixin,
    TransactionQuerysetMixin, TransferQuerysetMixin)
from ..backends import ProcessorError, ProcessorConnectionError
from ..utils import validate_redirect_url, datetime_or_now
from ..forms import (BankForm, CartPeriodsForm, CreditCardForm,
    ImportTransactionForm, RedeemCouponForm, WithdrawForm)
from ..mixins import (ChargeMixin, DateRangeMixin, OrganizationMixin,
    ProviderMixin)
from ..models import (Organization, CartItem, Coupon, Plan, Transaction,
    Subscription, get_broker)
from ..humanize import (as_money, describe_buy_periods, match_unlock,
    DESCRIBE_UNLOCK_NOW, DESCRIBE_UNLOCK_LATER)
from ..utils import product_url
from ..views import session_cart_to_database
from ..views.download import CSVDownloadView


LOGGER = logging.getLogger(__name__)


class BankMixin(OrganizationMixin):
    """
    Adds bank information to the context.
    """

    def get_context_data(self, **kwargs):
        context = super(BankMixin, self).get_context_data(**kwargs)
        try:
            context.update(self.get_organization().retrieve_bank())
        except ProcessorConnectionError, err:
            LOGGER.exception(err)
            messages.error(self.request,
                "Unable to communicate with Payment Processor. We are aware\
                of the issue and working on it. Thank you for your patience.")
        return context


class CardFormMixin(OrganizationMixin):

    form_class = CreditCardForm
    organization_url_kwarg = 'organization'

    def get_initial(self):
        """
        Populates place order forms with the organization address
        whenever possible.
        """
        self.customer = self.get_organization()
        kwargs = super(CardFormMixin, self).get_initial()
        provider = get_broker()
        if self.customer.country:
            country = self.customer.country
        else:
            country = provider.country
        if self.customer.region:
            region = self.customer.region
        else:
            region = provider.region
        kwargs.update({'card_name': self.customer.full_name,
                       'card_city': self.customer.locality,
                       'card_address_line1': self.customer.street_address,
                       'country': country,
                       'region': region,
                       'card_address_zip': self.customer.postal_code})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(CardFormMixin, self).get_context_data(**kwargs)
        try:
            context.update(self.customer.retrieve_card())
        except ProcessorConnectionError:
            messages.error(self.request, "The payment processor is "\
                "currently unreachable. Sorry for the inconvienience.")
        return context


class BankUpdateView(BankMixin, UpdateView):
    """
    Update the authentication tokens to connect to the deposit account
    handled by the processor or bank information used to transfer funds
    to the provider.

    Template:

    To edit the layout of this page, create a local \
    ``saas/billing/bank.html`` (`example <https://github.com/djaodjin/\
djaodjin-saas/tree/master/saas/templates/saas/billing/bank.html>`__).

    Template context:
      - ``STRIPE_CLIENT_ID`` client_id to send to stripe.com
      - ``STRIPE_PUB_KEY`` Public key to send to stripe.com
      - ``organization`` The provider of the plan
      - ``request`` The HTTP request object
    """
    form_class = BankForm
    template_name = 'saas/billing/bank.html'

    def get_context_data(self, **kwargs):
        context = super(BankUpdateView, self).get_context_data(**kwargs)
        context.update({'STRIPE_CLIENT_ID': settings.STRIPE_CLIENT_ID})
        return context

    def get_object(self, queryset=None):
        return self.get_organization()

    def form_valid(self, form):
        stripe_token = form.cleaned_data['stripeToken']
        if not stripe_token:
            messages.error(self.request, "Missing processor token.")
            return self.form_invalid(form)
        # Since all fields are optional, we cannot assume the card token
        # will be present (i.e. in case of erroneous POST request).
        self.object.update_bank(stripe_token)
        return super(BankUpdateView, self).form_valid(form)

    def get_success_url(self):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return redirect_path
        messages.success(self.request,
            "Connection to your deposit account was successfully updated")
        return reverse('saas_transfer_info', kwargs=self.get_url_kwargs())

    def get(self, request, *args, **kwargs):
        error = self.request.GET.get('error', None)
        if error:
            messages.error(self.request, "%s: %s" % (
                error, self.request.GET.get('error_description', "")))
        else:
            auth_code = request.GET.get('code', None)
            if auth_code:
                self.object.processor_backend.connect_auth(
                    self.object, auth_code)
                messages.success(self.request,
                  "Connection to your deposit account was successfully updated")
        return super(BankUpdateView, self).get(request, *args, **kwargs)


class InvoicablesFormMixin(OrganizationMixin):
    """
    Mixin a list of invoicables
    """

    @staticmethod
    def with_options(invoicables):
        """
        Returns ``True`` if any of the invoicables has at least two options
        available for the user.
        """
        for invoicable in invoicables:
            if len(invoicable['options']) > 1:
                return True
        return False

    def get_initial(self):
        kwargs = super(InvoicablesFormMixin, self).get_initial()
        for invoicable in self.invoicables:
            if invoicable['options']:
                kwargs.update({invoicable['name']: ""})
        return kwargs

    def get_form(self, form_class=None):
        self.invoicables = self.get_queryset()
        return super(InvoicablesFormMixin, self).get_form(form_class)

    def get_context_data(self, **kwargs):
        context = super(InvoicablesFormMixin, self).get_context_data(**kwargs)
        lines_amount = 0
        lines_unit = 'usd'
        for invoicable in self.invoicables:
            if len(invoicable['options']) > 0:
                # In case it is pure options, no lines.
                lines_unit = invoicable['options'][0].dest_unit
            for line in invoicable['lines']:
                lines_amount += line.dest_amount
                lines_unit = line.dest_unit
        context.update(self.get_redirect_path())
        context.update({'invoicables': self.invoicables,
                        "lines_amount": lines_amount,
                        "lines_unit": lines_unit})
        return context

    def get_redirect_path(self, **kwargs): #pylint: disable=unused-argument
        context = {}
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            context.update({REDIRECT_FIELD_NAME: redirect_path})
        return context


class CardInvoicablesFormMixin(CardFormMixin, InvoicablesFormMixin):
    """
    Create a charge for items that must be charged on submit.
    """

    # Implementation Node:
    #     All fields in CreditCardForm are optional to insure the form
    #     is never invalid and thus allow the same code to place an order
    #     with a total amount of zero.

    def form_valid(self, form):
        """
        If the form is valid we, optionally, checkout the cart items
        and charge the invoiced items which are due now.
        """
        # We remember the card by default. ``stripeToken`` is not present
        # when we are creating charges on a card already on file.
        if 'remember_card' in self.request.POST:
            # Workaround: Django does not take into account the value
            # of Field.initial anymore. Worse, it will defaults to False
            # when the field is not present in the POST.
            remember_card = form.cleaned_data['remember_card']
        else:
            remember_card = form.fields['remember_card'].initial
        stripe_token = form.cleaned_data['stripeToken']

        # deep copy the invoicables because we are updating the list in place
        # and we don't want to keep the edited state on a card failure.
        self.sole_provider = None
        invoicables = copy.deepcopy(self.invoicables)
        for invoicable in invoicables:
            # We use two conventions here:
            # 1. POST parameters prefixed with cart- correspond to an entry
            #    in the invoicables
            # 2. Amounts for each line in a entry are unique and are what
            #    is passed for the value of the matching POST parameter.
            plan = invoicable['subscription'].plan
            plan_key = invoicable['name']
            if self.sole_provider is None:
                self.sole_provider = plan.organization
            elif self.sole_provider != plan.organization:
                self.sole_provider = False
            if plan_key in form.cleaned_data:
                selected_line = int(form.cleaned_data[plan_key])
                for line in invoicable['options']:
                    if line.dest_amount == selected_line:
                        # Normalize unlock line description to
                        # "subscribe <plan> until ..."
                        if match_unlock(line.descr):
                            nb_periods = plan.period_number(line.descr)
                            line.descr = describe_buy_periods(plan,
                                plan.end_of_period(line.created_at, nb_periods),
                                nb_periods)
                        invoicable['lines'] += [line]

        try:
            self.charge = self.customer.checkout(
                invoicables, self.request.user,
                token=stripe_token, remember_card=remember_card)
            if self.charge and self.charge.invoiced_total_amount > 0:
                messages.info(self.request, "A receipt will be sent to"\
" %(email)s once the charge has been processed. Thank you."
                          % {'email': self.customer.email})
        except ProcessorError as err:
            messages.error(self.request, err)
            return self.form_invalid(form)
        return super(CardInvoicablesFormMixin, self).form_valid(form)

    def get_success_url(self):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if hasattr(self, 'charge') and self.charge:
            if redirect_path:
                return '%s?%s=%s' % (
                    reverse('saas_charge_receipt',
                        args=(self.charge.customer, self.charge.processor_key)),
                    REDIRECT_FIELD_NAME, redirect_path)
            return reverse('saas_charge_receipt',
                        args=(self.charge.customer, self.charge.processor_key))
        if redirect_path:
            return redirect_path
        if self.sole_provider:
            return product_url(self.sole_provider, self.customer)
        return reverse('saas_organization_profile', args=(self.customer,))


class CardUpdateView(CardFormMixin, FormView):
    """
    Page to update the Credit Card information associated to a subscriber.

    Template:

    To edit the layout of this page, create a local \
    ``saas/billing/card.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/billing/card.html>`__).

    Template context:
      - ``STRIPE_PUB_KEY`` Public key to send to stripe.com
      - ``organization`` The subscriber object
      - ``request`` The HTTP request object
    """

    template_name = 'saas/billing/card.html'

    def form_valid(self, form):
        stripe_token = form.cleaned_data['stripeToken']
        if stripe_token:
            # Since all fields are optional, we cannot assume the card token
            # will be present (i.e. in case of erroneous POST request).
            self.customer.update_card(stripe_token, self.request.user)
            messages.success(self.request,
                "Your credit card on file was sucessfully updated")
        return super(CardUpdateView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(CardUpdateView, self).get_context_data(**kwargs)
        context.update(self.get_redirect_path())
        return context

    def get_redirect_path(self, **kwargs): #pylint: disable=unused-argument
        context = {}
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if not redirect_path:
            redirect_path = validate_redirect_url(
                self.request.META.get('HTTP_REFERER', ''))
        if redirect_path:
            context.update({REDIRECT_FIELD_NAME: redirect_path})
        return context

    def get_success_url(self):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return redirect_path
        return reverse('saas_billing_info', args=(self.customer,))


class TransactionBaseView(DateRangeMixin, TemplateView):

    pass

class TransactionListView(CardFormMixin, TransactionBaseView):
    """
    This page shows a statement of ``Subscription`` orders, ``Charge``
    created and payment refunded.

    Template:

    To edit the layout of this page, create a local \
    ``saas/billing/index.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/billing/index.html>`__).
    You should insure the page will call back the
    :ref:`/api/billing/:organization/payments/ <api_billing_payments>`
    API end point to fetch the set of transactions.

    Template context:
      - ``balance_amount`` Amount due by the subscriber
      - ``balance_unit`` Unit the balance is expressed in (ex: usd)
      - ``organization`` The subscriber object
      - ``request`` The HTTP request object
    """

    template_name = 'saas/billing/index.html'

    def cache_fields(self, request):
        super(TransactionListView, self).cache_fields(request)
        self.customer = self.get_organization()
        if not request.GET.has_key('start_at'):
            self.start_at = (self.ends_at
                - self.customer.natural_subscription_period)

    def get_context_data(self, **kwargs):
        context = super(TransactionListView, self).get_context_data(**kwargs)
        balance_amount, balance_unit \
            = Transaction.objects.get_statement_balance(self.customer)
        if balance_amount < 0:
            # It is not straightforward to inverse a number in Django templates
            # so we do it with a convention on the ``humanize_money`` filter.
            balance_unit = '-%s' % balance_unit
        context.update({
            'organization': self.customer,
            'balance_amount': balance_amount,
            'balance_unit': balance_unit,
            'download_url': reverse(
                'saas_transactions_download', kwargs=self.get_url_kwargs())})
        return context


class TransactionDownloadView(SmartTransactionListMixin,
                              TransactionQuerysetMixin, CSVDownloadView):

    headings = [
        'Created At',
        'Amount',
        'Unit',
        'Description'
    ]

    def get_headings(self):
        return self.headings

    def get_filename(self):
        return datetime.now().strftime('transactions-%Y%m%d.csv')

    def queryrow_to_columns(self, transaction):
        org = self.get_organization()
        return [
            transaction.created_at.date(),
            '{:.2f}'.format((-1 if transaction.is_debit(org) else 1) *
                Decimal(transaction.dest_amount) / 100),
            transaction.dest_unit.encode('utf-8'),
            transaction.descr.encode('utf-8'),
        ]


class TransferListView(BankMixin, TransactionBaseView):
    """
    List of payments made to a provider or funds transfered out of the platform
    to the provider bank account.

    Template:

    To edit the layout of this page, create a local \
    ``saas/billing/transfers.html`` (`example <https://github.com/djaodjin/\
djaodjin-saas/tree/master/saas/templates/saas/billing/transfers.html>`__).
    You should insure the page will call back the
    :ref:`/api/billing/:organization/transfers/ <api_billing_transfers>`
    API end point to fetch the set of transactions.

    Template context:
      - ``organization`` The provider transactions refer to
      - ``request`` The HTTP request object
    """
    template_name = 'saas/billing/transfers.html'

    def get_context_data(self, **kwargs):
        self.organization = self.get_organization()
        context = super(TransferListView, self).get_context_data(**kwargs)
        context.update({'download_url': reverse(
                'saas_transfers_download', kwargs=self.get_url_kwargs())})
        return context


class TransferDownloadView(SmartTransactionListMixin,
                           TransferQuerysetMixin,
                           CSVDownloadView):

    headings = [
        'Created At',
        'Amount',
        'Unit',
        'Description'
    ]

    def get_filename(self):
        return datetime.now().strftime('funds-%Y%m%d.csv')

    def get_headings(self):
        return self.headings

    def queryrow_to_columns(self, transaction):
        org = self.get_organization()
        return [
            transaction.created_at.date(),
            '{:.2f}'.format((-1 if transaction.is_debit(org) else 1) *
                Decimal(transaction.dest_amount) / 100),
            transaction.dest_unit.encode('utf-8'),
            transaction.descr.encode('utf-8'),
        ]


class CartBaseView(InvoicablesFormMixin, FormView):
    """
    The main pupose of ``CartBaseView`` is generate an list of invoicables
    from ``CartItem`` records associated to a ``request.user``.

    The invoicables list is generated from the following schema::

        invoicables = [
                { "subscription": Subscription,
                  "lines": [Transaction, ...],
                  "options": [Transaction, ...],
                }, ...]


    Each subscription is either an actual record in the database (paying
    more periods on a subscription) or ``Subscription`` instance that only
    exists in memory but will be committed on checkout.

    The ``Transaction`` list keyed by "lines" contains in-memory instances
    for the invoice items that will be committed and charged when the order
    is finally placed.

    The ``Transaction`` list keyed by "options" contains in-memory instances
    the user can choose from. Options usually include various number of periods
    that can be pre-paid now for a discount. ex:

        $189.00 Subscription to streetside until 2014/11/07 (1 month)
        $510.30 Subscription to streetside until 2015/01/07 (3 months, 10% off)
        $907.20 Subscription to streetside until 2015/04/07 (6 months, 20% off)
    """

    def dispatch(self, *args, **kwargs):
        # We are not getting here without an authenticated user. It is time
        # to store the cart into the database.
        session_cart_to_database(self.request)
        return super(CartBaseView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(CartBaseView, self).get_context_data(**kwargs)
        context.update({'coupon_form': RedeemCouponForm()})
        return context

    @staticmethod
    def get_invoicable_options(subscription, created_at=None,
                               prorate_to=None, cart_item=None):
        """
        Return a set of lines that must charged Today and a set of choices
        based on current subscriptions that the user might be willing
        to charge Today.
        """
        #pylint: disable=too-many-locals
        created_at = datetime_or_now(created_at)
        option_items = []
        plan = subscription.plan
        # XXX Not charging setup fee, it complicates the design too much
        # at this point.

        # Pro-rated to billing cycle
        prorated_amount = 0
        if prorate_to:
            prorated_amount = plan.prorate_period(created_at, prorate_to)

        discount_percent = 0
        descr_suffix = None
        if cart_item:
            coupon = cart_item.coupon
            if coupon:
                discount_percent = coupon.percent
                if coupon.code.startswith('cpn_'):
                    descr_suffix = ', complimentary of %s' % cart_item.last_name
                else:
                    descr_suffix = '(code: %s)' % coupon.code

        first_periods_amount = plan.first_periods_amount(
            discount_percent=discount_percent,
            prorated_amount=prorated_amount)

        if first_periods_amount == 0:
            # We are having a freemium business models, no discounts.
            if not descr_suffix:
                descr_suffix = "free"
            option_items += [Transaction.objects.new_subscription_order(
                subscription, 1, prorated_amount, created_at,
                discount_percent=discount_percent,
                descr_suffix=descr_suffix)]

        elif plan.unlock_event:
            # Locked plans are free until an event.
            option_items += [Transaction.objects.new_subscription_order(
                subscription, 1, plan.period_amount, created_at,
                DESCRIBE_UNLOCK_NOW % {
                    'plan': plan, 'unlock_event': plan.unlock_event},
               discount_percent=discount_percent,
               descr_suffix=descr_suffix)]
            option_items += [Transaction.objects.new_subscription_order(
                subscription, 1, 0, created_at,
                DESCRIBE_UNLOCK_LATER % {
                        'amount': as_money(plan.period_amount, plan.unit),
                        'plan': plan, 'unlock_event': plan.unlock_event})]

        else:
            natural_periods = [1]
            if plan.advance_discount > 0:
                # Give a chance for discount when paying periods in advance
                if plan.interval == Plan.MONTHLY:
                    if plan.period_length == 1:
                        natural_periods = [1, 3, 6, 12]
                    elif plan.period_length == 4:
                        natural_periods = [1, 2, 3]
                    else:
                        natural_periods = [1, 2, 3, 4]
                else:
                    natural_periods = [1, 2, 3, 4]

            for nb_periods in natural_periods:
                if nb_periods > 1:
                    descr_suffix = ""
                    amount, discount_percent \
                        = subscription.plan.advance_period_amount(nb_periods)
                    if amount <= 0:
                        break # never allow to be completely free here.
                option_items += [Transaction.objects.new_subscription_order(
                    subscription, nb_periods, prorated_amount, created_at,
                    discount_percent=discount_percent,
                    descr_suffix=descr_suffix)]

        return option_items

    def get_queryset(self):
        #pylint: disable=too-many-locals
        self.customer = self.get_organization()
        created_at = datetime_or_now()
        prorate_to_billing = False
        prorate_to = None
        if prorate_to_billing:
            # XXX First we add enough periods to get the next billing date later
            # than created_at but no more than one period in the future.
            prorate_to = self.customer.billing_start
        invoicables = []
        for cart_item in CartItem.objects.get_cart(user=self.request.user):
            if cart_item.email:
                full_name = ' '.join([
                        cart_item.first_name, cart_item.last_name]).strip()
                for_descr = ', for %s (%s)' % (full_name, cart_item.email)
                organization_queryset = Organization.objects.filter(
                    email=cart_item.email)
                if organization_queryset.exists():
                    organization = organization_queryset.get()
                else:
                    organization = Organization(
                        full_name='%s %s' % (
                            cart_item.first_name, cart_item.last_name),
                        email=cart_item.email)
            else:
                for_descr = ''
                organization = self.customer
            try:
                # If we can extend a current ``Subscription`` we will.
                # XXX For each (organization, plan) there should not
                #     be overlapping timeframe [created_at, ends_at[,
                #     None-the-less, it might be a good idea to catch
                #     and throw a nice error message in case.
                subscription = Subscription.objects.get(
                    organization=organization, plan=cart_item.plan,
                    ends_at__gt=datetime_or_now())
            except Subscription.DoesNotExist:
                ends_at = prorate_to
                if not ends_at:
                    ends_at = created_at
                subscription = Subscription.objects.new_instance(
                    organization, cart_item.plan, ends_at=ends_at)
            lines = []
            options = self.get_invoicable_options(subscription,
                created_at=created_at, prorate_to=prorate_to,
                cart_item=cart_item)
            if cart_item.nb_periods > 0:
                # The number of periods was already selected so we generate
                # a line instead.
                for line in options:
                    plan = subscription.plan
                    nb_periods = plan.period_number(line.descr)
                    if nb_periods == cart_item.nb_periods:
                        # ``TransactionManager.new_subscription_order``
                        # will have created a ``Transaction``
                        # with the ultimate subscriber
                        # as payee. Overriding ``dest_organization`` here
                        # insures in all cases (bulk and direct buying),
                        # the transaction is recorded (in ``execute_order``)
                        # on behalf of the customer on the checkout page.
                        line.dest_organization = self.customer
                        line.descr += for_descr
                        lines += [line]
                        options = []
                        break
            invoicables += [{
                'name': cart_item.name, 'descr': cart_item.descr,
                'subscription': subscription,
                "lines": lines, "options": options}]
        return invoicables

    def get_success_url(self):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return '%s?%s=%s' % (
                reverse('saas_organization_cart', args=(self.customer,)),
                REDIRECT_FIELD_NAME, redirect_path)
        return reverse('saas_organization_cart', args=(self.customer,))


class CartPeriodsView(CartBaseView):
    """
    Optional page to pay multiple periods in advance.

    Template:

    To edit the layout of this page, create a local \
    ``saas/billing/cart-periods.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/billing/cart-periods.html>`__).

    Template context:
      - ``invoicables`` List of items to be invoiced (with options)
      - ``organization`` The provider of the product
      - ``request`` The HTTP request object
    """
    form_class = CartPeriodsForm
    template_name = 'saas/billing/cart-periods.html'

    def form_valid(self, form):
        """
        If the form is valid we, optionally, checkout the cart items
        and charge the invoiced items which are due now.
        """
        for invoicable in self.invoicables:
            # We use two conventions here:
            # 1. POST parameters prefixed with cart- correspond to an entry
            #    in the invoicables
            # 2. Amounts for each line in a entry are unique and are what
            #    is passed for the value of the matching POST parameter.
            plan = invoicable['subscription'].plan
            plan_key = invoicable['name']
            if plan_key in form.cleaned_data:
                selected_line = int(form.cleaned_data[plan_key])
                for line in invoicable['options']:
                    if line.dest_amount == selected_line:
                        queryset = CartItem.objects.get_cart(
                            user=self.request.user).filter(plan=plan)
                        for cart_item in queryset:
                            cart_item.nb_periods \
                                = plan.period_number(line.descr)
                            cart_item.save()
        return super(CartPeriodsView, self).form_valid(form)

    @property
    def cart_items(self):
        return CartItem.objects.get_cart(user=self.request.user)

    def get(self, request, *args, **kwargs):
        if not self.cart_items.exists():
            messages.info(self.request,
              "Your Cart is empty. Please add some items to your cart before"
" you check out.")
            return http.HttpResponseRedirect(reverse('saas_cart_plan_list'))
        return super(CartPeriodsView, self).get(request, *args, **kwargs)


class CartSeatsView(CartPeriodsView):
    """
    Optional page to subcribe multiple organizations to a ``Plan`` while paying
    through through a third-party ``Organization`` (i.e. self.customer).

    Template:

    To edit the layout of this page, create a local \
    ``saas/billing/cart-seats.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/billing/cart-seats.html>`__).

    Template context:
      - ``invoicables`` List of items to be invoiced (with options)
      - ``organization`` The provider of the product
      - ``request`` The HTTP request object
    """
    form_class = CartPeriodsForm # XXX
    template_name = 'saas/billing/cart-seats.html'

    def get(self, request, *args, **kwargs):
        self.customer = self.get_organization()
        if self.cart_items.filter(nb_periods=0).exists():
            # If nb_periods == 0, we will present multiple options
            # to the user. We also rely on discount_percent
            # to be positive, otherwise it looks really weird
            # (i.e. one option).
            return http.HttpResponseRedirect(
                reverse('saas_cart_periods', args=(self.customer,)))
        return super(CartSeatsView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(CartSeatsView, self).get_context_data(**kwargs)
        context.update({
                'is_bulk_buyer': self.get_organization().is_bulk_buyer})
        return context


class CartView(CardInvoicablesFormMixin, CartSeatsView):
    """
    ``CartView`` derives from ``CartSeatsView`` which itself derives from
    ``CartPeriodsView``, all of which overrides the ``get`` method to redirect
    to the appropriate step in the order pipeline no matter the original entry
    point.
    """

    template_name = 'saas/billing/cart.html'

    def get(self, request, *args, **kwargs):
        """
        Prompt the user to enter her credit card and place an order.

        On POST, the credit card will be charged and the organization
        subscribed to the plans ordered.

        Template:

        To edit the layout of this page, create a local \
        ``saas/billing/cart.html`` (`example <https://github.com/djaodjin/\
djaodjin-saas/tree/master/saas/templates/saas/billing/cart.html>`__).
        This template is responsible to create a token on Stripe that will
        then be posted back to the site.

        Template context:
          - ``STRIPE_PUB_KEY`` Public key to send to stripe.com
          - ``invoicables`` List of items to be invoiced (with options)
          - ``organization`` The provider of the product
          - ``request`` The HTTP request object
        """
        self.customer = self.get_organization()
        if (self.customer.is_bulk_buyer and
            self.cart_items.filter(
                Q(email__isnull=True) | Q(email='')).exists()):
            # A bulk buyer customer can buy subscriptions for other people.
            return http.HttpResponseRedirect(
                reverse('saas_cart_seats', args=(self.customer,)))
        return super(CartView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(CartView, self).get_context_data(**kwargs)
        context.update({'is_bulk_buyer': False})
        return context


class ChargeReceiptView(ChargeMixin, DetailView):
    """
    Display a receipt for a ``Charge``.

    Template:

    To edit the layout of this page, create a local \
    ``saas/billing/receipt.html`` (`example <https://github.com/djaodjin/\
djaodjin-saas/tree/master/saas/templates/saas/billing/receipt.html>`__).

    Template context:
      - ``charge`` The charge object
      - ``organization`` The provider of the product
      - ``request`` The HTTP request object

    This page will be accessible in the payment flow as well as through
    a subscriber profile interface. The template should take both usage
    under consideration.
    """
    # XXX We might want to pass a url get parameter to distinguish here
    # between access through profile or not.

    template_name = 'saas/billing/receipt.html'


class CouponListView(OrganizationMixin, ListView):
    """
    View to manage discounts (i.e. ``Coupon``)

    Template:

    To edit the layout of this page, create a local \
    ``saas/billing/coupons.html`` (`example <https://github.com/\
djaodjin/djaodjin-saas/tree/master/saas/templates/saas/billing/\
coupons.html>`__).
    You should insure the page will call back the
    :ref:`/api/billing/:organization/coupons/ <api_billing_coupons>`
    API end point to fetch the set of coupons for the provider organization.


    Template context:
      - ``organization`` The provider for the coupons
      - ``request`` The HTTP request object
    """
    model = Coupon
    template_name = 'saas/billing/coupons.html'


class RedeemCouponView(ProviderMixin, FormView):
    """
    Stores a ``Coupon`` into the session for further use in the checkout
    pipeline.
    """
    template_name = 'saas/redeem.html'
    form_class = RedeemCouponForm

    def form_valid(self, form):
        redeemed = Coupon.objects.active(
            self.get_organization(), form.cleaned_data['code']).first()
        if redeemed is None:
            form.add_error('code', 'Invalid code')
            return super(RedeemCouponView, self).form_invalid(form)
        self.request.session['redeemed'] = redeemed.code
        return super(RedeemCouponView, self).form_valid(form)

    def get_success_url(self):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return redirect_path
        if self.request.user.is_authenticated():
            return reverse('saas_cart')
        return reverse('saas_cart_plan_list')


class BalanceView(CardInvoicablesFormMixin, FormView):
    """
    Set of invoicables for all subscriptions which have a balance due.

    While ``CartView`` generates the invoicables from the ``CartItem``
    model, ``BalanceView`` generates the invoicables from ``Subscription``
    for which the amount payable by the customer is positive.

    The invoicables list is generated from the following schema::

        invoicables = [
                { "subscription": Subscription,
                  "name": "",
                  "descr": "",
                  "lines": [Transaction, ...],
                  "options": [Transaction, ...],
                }, ...]
    """
    plan_url_kwarg = 'subscribed_plan'
    template_name = 'saas/billing/balance.html'

    @staticmethod
    def get_invoicable_options(subscription, created_at=None,
                               prorate_to=None, cart_item=None):
        #pylint: disable=unused-argument
        payable = Transaction.objects.new_subscription_statement(
            subscription, created_at)
        if payable.dest_amount > 0:
            later = Transaction.objects.new_subscription_later(
                subscription, created_at)
            return [payable, later]
        return []

    def get_queryset(self):
        """
        GET displays the balance due by a subscriber.

        Template:

        To edit the layout of this page, create a local \
        ``saas/billing/balance.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/billing/balance.html>`__).

        Template context:
          - ``STRIPE_PUB_KEY`` Public key to send to stripe.com
          - ``invoicables`` List of items to be invoiced (with options)
          - ``organization`` The provider of the product
          - ``request`` The HTTP request object

        POST attempts to charge the card for the balance due.
        """
        self.customer = self.get_organization()
        invoicables = []
        created_at = datetime_or_now()
        for subscription in Subscription.objects.active_for(self.customer):
            options = self.get_invoicable_options(subscription,
                created_at=created_at)
            if len(options) > 0:
                invoicables += [{
                    'subscription': subscription,
                    'name': 'cart-%s' % subscription.plan.slug,
                    'lines': [],
                    'options': options}]
        return invoicables

    def get_subscription(self):
        return get_object_or_404(Subscription,
            organization=self.get_organization(),
            plan__slug=self.kwargs.get(self.plan_url_kwarg))


class WithdrawView(BankMixin, FormView):
    """
    Initiate the transfer of funds from the platform to a provider bank account.

    Template:

    To edit the layout of this page, create a local \
    ``saas/billing/withdraw.html`` (`example <https://github.com/djaodjin/\
djaodjin-saas/tree/master/saas/templates/saas/billing/withdraw.html>`__).

    Template context:
      - ``STRIPE_PUB_KEY`` Public key to send to stripe.com
      - ``organization`` The subscriber object
      - ``request`` The HTTP request object
    """

    form_class = WithdrawForm
    template_name = 'saas/billing/withdraw.html'

    def get_initial(self):
        self.organization = self.get_organization()
        kwargs = super(WithdrawView, self).get_initial()
        balance = self.organization.withdraw_available()
        available_amount = balance['amount']
        kwargs.update({
            'amount': (available_amount / 100.0) if balance > 0 else 0})
        return kwargs

    def form_valid(self, form):
        stripe_token = form.cleaned_data['stripeToken']
        if stripe_token:
            # Since all fields are optional, we cannot assume the card token
            # will be present (i.e. in case of erroneous POST request).
            self.organization.update_bank(stripe_token)
            messages.success(self.request,
                "Your bank on file was sucessfully updated")
        amount_withdrawn = int(float(form.cleaned_data['amount']) * 100)
        self.organization.withdraw_funds(amount_withdrawn, self.request.user)
        return super(WithdrawView, self).form_valid(form)

    def get_success_url(self):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return redirect_path
        return reverse('saas_transfer_info', kwargs=self.get_url_kwargs())


class ImportTransactionsView(ProviderMixin, FormView):
    """
    Insert transactions that were done offline for the purpose of computing
    accurate metrics.

    Template:

    To edit the layout of this page, create a local \
    ``saas/billing/import.html`` (`example <https://github.com/djaodjin/\
djaodjin-saas/tree/master/saas/templates/saas/billing/import.html>`__).

    Template context:
      - ``organization`` The provider object
      - ``request`` The HTTP request object
    """

    form_class = ImportTransactionForm
    template_name = 'saas/billing/import.html'

    def form_valid(self, form):
        subscriber, plan = form.cleaned_data['subscription'].split(
            Subscription.SEP)
        subscriber = Organization.objects.filter(slug=subscriber).first()
        if subscriber is None:
            form.add_error(None, "Invalid subscriber")
        plan = Plan.objects.filter(
            slug=plan, organization=self.get_organization()).first()
        if plan is None:
            form.add_error(None, "Invalid plan")
        if form.errors:
            # We haven't found either the subscriber or the plan.
            return self.form_invalid(form)
        subscription = Subscription.objects.active_for(
            organization=subscriber).filter(plan=plan).first()
        Transaction.objects.offline_payment(
            subscription, form.cleaned_data['amount'],
            descr=form.cleaned_data['descr'], user=self.request.user,
            created_at=form.cleaned_data['created_at'])
        return super(ImportTransactionsView, self).form_valid(form)

    def get_success_url(self):
        return reverse('saas_transfer_info', kwargs=self.get_url_kwargs())

