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
The two primary views to place an order are ``CartView`` and ``BalanceView``.
``CartView`` is used to implement the checkout and place a new order while
``BalanceView`` is used to pay an ``Organization`` balance due, either because
a charge wasn't sucessful and/or the provider implements a subscribe-pay-later
policy.

1. ``CartView`` for items in the cart, create new subscriptions
   or pay in advance.

2. ``BalanceView`` for subscriptions with balance dues
"""

import copy, logging

from django import http
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.urlresolvers import reverse
from django.db import IntegrityError
from django.db.models import Q
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, FormView, ListView

from saas.backends import PROCESSOR_BACKEND, ProcessorError
from saas.utils import validate_redirect_url, datetime_or_now
from saas.forms import (BankForm, CartPeriodsForm, CreditCardForm,
    RedeemCouponForm, WithdrawForm)
from saas.mixins import ChargeMixin, OrganizationMixin, ProviderMixin
from saas.models import (Organization, CartItem, Coupon, Plan, Transaction,
    Subscription)
from saas.humanize import (as_money, describe_buy_periods, match_unlock,
    DESCRIBE_UNLOCK_NOW, DESCRIBE_UNLOCK_LATER)

LOGGER = logging.getLogger(__name__)

def _session_cart_to_database(request):
    """
    Transfer all the items in the cart stored in the session into proper
    records in the database.
    """
    if request.session.has_key('cart_items'):
        for item in request.session['cart_items']:
            item['plan'] = Plan.objects.get(slug=item['plan'])
            item['user'] = request.user
            try:
                CartItem.objects.create(**item) #pylint: disable=star-args
            except IntegrityError: #pylint: disable=catching-non-exception
                # This might happen during testing of the place order
                # through the test driver. Either way, if the item is
                # already in the cart, it is OK to forget about this
                # exception.
                LOGGER.warning('%s is already in cart db.', item)
        del request.session['cart_items']


class BankMixin(ProviderMixin):
    """
    Adds bank information to the context.
    """

    def get_context_data(self, **kwargs):
        context = super(BankMixin, self).get_context_data(**kwargs)
        context.update(PROCESSOR_BACKEND.retrieve_bank(self.get_organization()))
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
        kwargs.update({'card_name': self.customer.full_name,
                       'card_city': self.customer.locality,
                       'card_address_line1': self.customer.street_address,
                       'country': self.customer.country,
                       'region': self.customer.region,
                       'card_address_zip': self.customer.postal_code})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(CardFormMixin, self).get_context_data(**kwargs)
        context.update(PROCESSOR_BACKEND.retrieve_card(self.customer))
        if not context['STRIPE_PUB_KEY']:
            # XXX helpful for debugging test infrastructure.
            messages.error(self.request, "STRIPE_PUB_KEY is not defined.")
        return context


class BankUpdateView(BankMixin, FormView):
    """
    The bank information is used to transfer funds to those organization
    who are providers on the marketplace.
    """

    form_class = BankForm
    template_name = 'saas/bank_update.html'

    def form_valid(self, form):
        self.organization = self.get_organization()
        stripe_token = form.cleaned_data['stripeToken']
        if stripe_token:
            # Since all fields are optional, we cannot assume the card token
            # will be present (i.e. in case of erroneous POST request).
            self.organization.update_bank(stripe_token)
            messages.success(self.request,
                "Your bank on file was sucessfully updated")
        return super(BankUpdateView, self).form_valid(form)

    def get_success_url(self):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return redirect_path
        return reverse('saas_transfer_info', args=(self.organization,))


class InvoicablesFormMixin(OrganizationMixin):
    """
    Mixin a list of invoicables
    """

    def get_initial(self):
        kwargs = super(InvoicablesFormMixin, self).get_initial()
        for invoicable in self.invoicables:
            if invoicable['options']:
                kwargs.update({invoicable['name']: ""})
        return kwargs

    def get_form(self, form_class):
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
        # XXX We always remember the card instead of taking input
        # from the form.cleaned_data['remember_card'] field.
        remember_card = True
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
                            line.descr = describe_buy_periods(
                                plan, plan.end_of_period(
                                    line.created_at, line.orig_amount),
                                line.orig_amount)
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
                        args=(self.charge.customer, self.charge.processor_id)),
                    REDIRECT_FIELD_NAME, redirect_path)
            return reverse('saas_charge_receipt',
                        args=(self.charge.customer, self.charge.processor_id))
        if redirect_path:
            return redirect_path
        if self.sole_provider:
            # XXX product_default_start is not defined in url patterns.
            return '/%(organization)s/app/%(subscriber)s/' % {
                'organization': self.sole_provider,
                'subscriber': self.customer}
        return reverse('saas_organization_profile', args=(self.customer,))


class CardUpdateView(CardFormMixin, FormView):

    template_name = 'billing/card.html'

    def form_valid(self, form):
        stripe_token = form.cleaned_data['stripeToken']
        if stripe_token:
            # Since all fields are optional, we cannot assume the card token
            # will be present (i.e. in case of erroneous POST request).
            self.customer.update_card(stripe_token)
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


class TransactionListView(OrganizationMixin, ListView):
    """
    This page shows the subscriptions an Organization paid for
    as well as payment refunded.
    """

    paginate_by = 10
    template_name = 'billing/index.html'

    def get_queryset(self):
        """
        Get the list of transactions for this organization.
        """
        self.customer = self.get_organization()
        queryset = Transaction.objects.filter(
            (Q(dest_organization=self.customer)
             & (Q(dest_account=Transaction.PAYABLE) # Only customer side
                | Q(dest_account=Transaction.EXPENSES)))
            |(Q(orig_organization=self.customer)
              & Q(orig_account=Transaction.REFUNDED))).order_by('-created_at')
        return queryset

    def get_context_data(self, **kwargs):
        context = super(TransactionListView, self).get_context_data(**kwargs)
        context.update({'organization': self.customer})
        balance_amount, balance_unit \
            = Transaction.objects.get_organization_balance(self.customer)
        if balance_amount < 0:
            # It is not straightforward to inverse a number in Django templates
            # so we do it with a convention on the ``humanize_money`` filter.
            balance_unit = '-%s' % balance_unit
        context.update({'organization': self.customer,
                        'balance_amount': balance_amount,
                        'balance_unit': balance_unit})
        return context


class TransferListView(BankMixin, ListView):
    """
    List of transfers from processor to an organization bank account.
    """

    paginate_by = 10
    template_name = 'saas/transfer_list.html'

    def get_queryset(self):
        """
        Get the list of transactions for this organization.
        """
        self.organization = self.get_organization()
        queryset = Transaction.objects.filter(
            # All transactions involving Funds
            ((Q(orig_organization=self.organization)
              & Q(orig_account=Transaction.FUNDS))
            | (Q(dest_organization=self.organization)
              & Q(dest_account=Transaction.FUNDS)))).order_by('-created_at')
        return queryset

    def get_context_data(self, **kwargs):
        context = super(TransferListView, self).get_context_data(**kwargs)
        balance_amount, balance_unit \
            = Transaction.objects.get_organization_balance(
            self.organization, Transaction.FUNDS)
        context.update({'balance_amount': balance_amount,
                        'balance_unit': balance_unit})
        return context


class CartBaseView(InvoicablesFormMixin, FormView):
    """
    The main pupose of ``CartBaseView`` is generate an list of invoicables
    from ``CartItem`` records associated to a ``request.user``.

    The invoicables list is generated from the following schema:

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
        _session_cart_to_database(self.request)
        return super(CartBaseView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(CartBaseView, self).get_context_data(**kwargs)
        context.update({'coupon_form': RedeemCouponForm()})
        return context

    @staticmethod
    def get_invoicable_options(subscription,
                              created_at=None, prorate_to=None, coupon=None):
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
        if coupon:
            discount_percent = coupon.percent

        if plan.period_amount == 0:
            # We are having a freemium business models, no discounts.
            option_items += [subscription.create_order(1, prorated_amount,
                created_at, "free")]

        elif plan.unlock_event:
            # Locked plans are free until an event.
            option_items += [subscription.create_order(1, plan.period_amount,
               created_at, DESCRIBE_UNLOCK_NOW % {
                        'plan': plan, 'unlock_event': plan.unlock_event},
               discount_percent=discount_percent)]
            option_items += [subscription.create_order(1, 0,
               created_at, DESCRIBE_UNLOCK_LATER % {
                        'amount': as_money(plan.period_amount, plan.unit),
                        'plan': plan, 'unlock_event': plan.unlock_event})]

        elif plan.interval == Plan.MONTHLY:
            # Give a change for discount when paying periods in advance
            for nb_periods in [1, 3, 6, 12]:
                option_items += [subscription.create_order(
                    nb_periods, prorated_amount, created_at,
                    discount_percent=discount_percent)]
                discount_percent += 10
                if discount_percent >= 100:
                    discount_percent = 100

        elif plan.interval == Plan.YEARLY:
            # Give a change for discount when paying periods in advance
            for nb_periods in [1]: # XXX disabled discount until configurable.
                option_items += [subscription.create_order(
                    nb_periods, prorated_amount, created_at,
                    discount_percent=discount_percent)]
                discount_percent += 10
                if discount_percent >= 100:
                    discount_percent = 100

        else:
            raise IntegrityError(#pylint: disable=nonstandard-exception
                "Cannot use interval specified for plan '%s'" % plan)

        return option_items

    def get_queryset(self):
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
                subscription = Subscription.objects.get(
                    organization=organization, plan=cart_item.plan)
            except Subscription.DoesNotExist:
                ends_at = prorate_to
                if not ends_at:
                    ends_at = created_at
                subscription = Subscription.objects.new_instance(
                    organization, cart_item.plan, ends_at=ends_at)
            lines = []
            options = self.get_invoicable_options(subscription, created_at,
                prorate_to=prorate_to, coupon=cart_item.coupon)
            if cart_item.nb_periods > 0:
                # The number of periods was already selected so we generate
                # a line instead.
                for line in options:
                    if line.orig_amount == cart_item.nb_periods:
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
    """
    form_class = CartPeriodsForm
    template_name = 'saas/cart_periods.html'

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
                            cart_item.nb_periods = line.orig_amount
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
    """
    form_class = CartPeriodsForm # XXX
    template_name = 'saas/cart_seats.html'

    def get(self, request, *args, **kwargs):
        self.customer = self.get_organization()
        if self.cart_items.filter(nb_periods=0).exists():
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

    template_name = 'billing/cart.html'

    def get(self, request, *args, **kwargs):
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
    Display a receipt for a created charge.
    """
    template_name = 'billing/receipt.html'


class CouponListView(ProviderMixin, ListView):
    """
    View to manage coupons
    """
    model = Coupon


class BalanceView(CardInvoicablesFormMixin, FormView):
    """
    Set of invoicables for all subscriptions which have a balance due.

    While ``CartView`` generates the invoicables from the ``CartItem``
    model, ``BalanceView`` generates the invoicables from ``Subscription``
    for which the amount payable by the customer is positive.

    The invoicables list is generated from the following schema:

        invoicables = [
                { "subscription": Subscription,
                  "name": "",
                  "descr": "",
                  "lines": [Transaction, ...],
                  "options": [Transaction, ...],
                }, ...]
    """

    plan_url_kwarg = 'subscribed_plan'
    template_name = 'billing/balance.html'

    @staticmethod
    def get_invoicable_options(subscription, created_at=None, prorate_to=None):
        #pylint: disable=unused-argument
        payable = Transaction.objects.get_subscription_payable(
            subscription, created_at)
        if payable.dest_amount > 0:
            later = Transaction.objects.get_subscription_later(
                subscription, created_at)
            return [payable, later]
        return []

    def get_queryset(self):
        self.customer = self.get_organization()
        invoicables = []
        created_at = datetime_or_now()
        for subscription in Subscription.objects.active_for(self.customer):
            options = self.get_invoicable_options(subscription, created_at)
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

    form_class = WithdrawForm
    template_name = 'saas/withdraw_form.html'

    def get_initial(self):
        self.organization = self.get_organization()
        kwargs = super(WithdrawView, self).get_initial()
        balance, _ = Transaction.objects.get_organization_balance(
            self.organization, Transaction.FUNDS)
        kwargs.update({'amount': (- balance / 100.0) if balance < 0 else 0})
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
        return reverse('saas_transfer_info', args=(self.organization,))
