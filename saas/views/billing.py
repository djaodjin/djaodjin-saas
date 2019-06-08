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
from __future__ import unicode_literals

import copy, logging

from django import http
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.db import transaction
from django.db.models import Q
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.views.generic import (DetailView, FormView, ListView, TemplateView,
    UpdateView)
from django.utils.http import urlencode
from django.utils import six

from .. import settings
from ..compat import is_authenticated, reverse
from ..backends import ProcessorError, ProcessorConnectionError
from ..decorators import _insert_url, _valid_manager
from ..forms import (BankForm, CartPeriodsForm, CreditCardForm,
    ImportTransactionForm, RedeemCouponForm, VTChargeForm, WithdrawForm)
from ..humanize import describe_buy_periods, match_unlock
from ..mixins import (CartMixin, ChargeMixin, DateRangeContextMixin,
    OrganizationMixin, ProviderMixin, product_url)
from ..models import (CartItem, Charge, Coupon, Organization, Plan, Price,
    Subscription, Transaction, UseCharge, get_broker)
from ..utils import (datetime_or_now, is_broker, update_context_urls,
    validate_redirect_url)
from ..views import session_cart_to_database


LOGGER = logging.getLogger(__name__)


class BankMixin(ProviderMixin):
    """
    Adds bank information to the context.
    """

    @property
    def processor_token_id(self):
        return get_broker().processor_backend.token_id

    def get_context_data(self, **kwargs):
        context = super(BankMixin, self).get_context_data(**kwargs)
        context.update(self.provider.get_deposit_context())
        return context


class CardFormMixin(OrganizationMixin):

    form_class = CreditCardForm

    @property
    def processor_token_id(self):
        return get_broker().processor_backend.token_id

    def get_initial(self):
        """
        Populates place order forms with the organization address
        whenever possible.
        """
        kwargs = super(CardFormMixin, self).get_initial()
        provider = get_broker()
        if self.organization.country:
            country = self.organization.country
        else:
            country = provider.country
        if self.organization.region:
            region = self.organization.region
        else:
            region = provider.region
        kwargs.update({'card_name': self.organization.full_name,
                       'card_city': self.organization.locality,
                       'card_address_line1': self.organization.street_address,
                       'country': country,
                       'region': region,
                       'card_address_zip': self.organization.postal_code})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(CardFormMixin, self).get_context_data(**kwargs)
        try:
            context.update(self.organization.retrieve_card())
        except ProcessorConnectionError:
            messages.error(self.request, _("The payment processor is "\
                "currently unreachable. Sorry for the inconvienience."))
        update_context_urls(context,
            {'organization': {
                'update_card': reverse(
                    'saas_update_card', args=(self.organization,))}})
        return context


class BankUpdateView(BankMixin, UpdateView):

    form_class = BankForm
    template_name = 'saas/billing/bank.html'

    def get_context_data(self, **kwargs):
        context = super(BankUpdateView, self).get_context_data(**kwargs)
        context.update({'force_update': True})
        update_context_urls(context, {'provider': {
            'deauthorize_bank': reverse(
                'saas_deauthorize_bank', args=(self.provider,))}})
        return context

    def get_object(self, queryset=None):
        return self.provider

    def get_success_url(self):
        messages.success(self.request,
            _("Connection to your deposit account was successfully updated."))
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return redirect_path
        return reverse('saas_transfer_info', kwargs=self.get_url_kwargs())


class BankDeAuthorizeView(BankUpdateView):
    """
    Removes access to deposit funds into the bank account.
    """
    def form_valid(self, form):
        self.object.update_bank(None)
        return super(BankDeAuthorizeView, self).form_valid(form)


class BankAuthorizeView(BankUpdateView):
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

    def form_valid(self, form):
        processor_token = form.cleaned_data[self.processor_token_id]
        if not processor_token:
            messages.error(self.request, _("Missing processor token."))
            return self.form_invalid(form)
        # Since all fields are optional, we cannot assume the card token
        # will be present (i.e. in case of erroneous POST request).
        self.object.update_bank(processor_token)
        return super(BankAuthorizeView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(BankAuthorizeView, self).get_context_data(**kwargs)
        update_context_urls(context, {
            'authorize_processor': self.get_authorize_url()})
        return context

    def get_authorize_url(self):
        provider = self.organization
        return provider.processor_backend.get_authorize_url(provider)

    def get(self, request, *args, **kwargs):
        error = self.request.GET.get('error', None)
        if error:
            messages.error(self.request, "%s: %s" % (
                error, self.request.GET.get('error_description', "")))
        else:
            auth_code = request.GET.get('code', None)
            if auth_code:
                try:
                    self.object = self.get_object()
                    self.object.processor_backend.connect_auth(
                        self.object, auth_code)
                    self.object.save()
                    messages.success(self.request, _("Connection to your"\
                        " deposit account was successfully updated."))
                except ProcessorError as err:
                    self.object.save()
                    LOGGER.exception("There was an error with processor"\
                        " authentication (%s).", err)
                    messages.error(self.request, _("An error occured while"\
                        " saving your deposit account settings."))
                # XXX maybe redirect to same page here to remove query params.
        return super(BankAuthorizeView, self).get(request, *args, **kwargs)


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
        context.update(self.get_redirect_path())
        lines_amount = 0
        lines_unit = settings.DEFAULT_UNIT
        for invoicable in self.invoicables:
            if len(invoicable['options']) > 0:
                # In case it is pure options, no lines.
                lines_unit = invoicable['options'][0].dest_unit
                invoicable['selected_option'] = 1
                for rank, line in enumerate(invoicable['options']):
                    setattr(line, 'rank', rank + 1)
            for line in invoicable['lines']:
                lines_amount += line.dest_amount
                lines_unit = line.dest_unit
        current_plan = None
        self.invoicables.sort(
            key=lambda invoicable: str(invoicable['subscription']))
        for invoicable in self.invoicables:
            plan = invoicable['subscription'].plan
            invoicable['is_changed'] = (
                current_plan is not None and plan != current_plan)
            current_plan = plan
        context.update({'invoicables': self.invoicables,
            'lines_price': Price(lines_amount, lines_unit)})
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
        data = form.cleaned_data
        # We remember the card by default. ``processor_token_id`` is not present
        # when we are creating charges on a card already on file.
        if 'remember_card' in self.request.POST:
            # Workaround: Django does not take into account the value
            # of Field.initial anymore. Worse, it will defaults to False
            # when the field is not present in the POST.
            remember_card = data['remember_card']
        else:
            remember_card = form.fields['remember_card'].initial
        processor_token = data[self.processor_token_id]
        self.organization.update_address_if_empty(country=data.get('country'),
            region=data.get('region'), locality=data.get('card_city'),
            street_address=data.get('card_address_line1'),
            postal_code=data.get('card_address_zip'))

        # deep copy the invoicables because we are updating the list in place
        # and we don't want to keep the edited state on a card failure.
        self.sole_provider = None
        if not self.invoicables:
            LOGGER.error("No invoicables for user %s", self.request.user,
                extra={'request': self.request})
            messages.info(self.request,
              _("There are no items invoicable at this point. Please select an"\
" item before checking out."))
            return http.HttpResponseRedirect(reverse('saas_cart_plan_list'))
        invoicables = copy.deepcopy(self.invoicables)
        for invoicable in invoicables:
            # We use the following convention here:
            # POST parameters prefixed with cart- correspond to an entry
            # in the invoicables
            plan = invoicable['subscription'].plan
            plan_key = invoicable['name']
            if self.sole_provider is None:
                self.sole_provider = plan.organization
            elif self.sole_provider != plan.organization:
                self.sole_provider = False
            if plan_key in data:
                selected_line = int(data[plan_key]) - 1
                if (selected_line >= 0 and
                    selected_line < len(invoicable['options'])):
                    line = invoicable['options'][selected_line]
                    # Normalize unlock line description to
                    # "subscribe <plan> until ..."
                    if match_unlock(line.descr):
                        nb_periods = plan.period_number(line.descr)
                        line.descr = describe_buy_periods(plan,
                            plan.end_of_period(line.created_at, nb_periods),
                            nb_periods)
                    invoicable['lines'] += [line]

        try:
            self.charge = self.organization.checkout(
                invoicables, self.request.user,
                token=processor_token, remember_card=remember_card)
            if self.charge and self.charge.invoiced_total.amount > 0:
                messages.info(self.request, _("A receipt will be sent to"\
" %(email)s once the charge has been processed. Thank you.")
                          % {'email': self.organization.email})
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
            return product_url(self.sole_provider, self.organization,
                request=self.request)
        return product_url(get_broker(), self.organization,
            request=self.request)


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
        processor_token = form.cleaned_data[self.processor_token_id]
        if processor_token:
            # Since all fields are optional, we cannot assume the card token
            # will be present (i.e. in case of erroneous POST request).
            try:
                self.organization.update_card(
                    processor_token, self.request.user)
                messages.success(self.request,
                    _("Your credit card on file was sucessfully updated"))
            except ProcessorError as err:
                messages.error(self.request, err)
                return self.form_invalid(form)
        return super(CardUpdateView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(CardUpdateView, self).get_context_data(**kwargs)
        context.update(self.get_redirect_path())
        context.update({'force_update': True})
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
        return reverse('saas_billing_info', args=(self.organization,))


class TransactionBaseView(DateRangeContextMixin, TemplateView):

    def get_context_data(self, **kwargs):
        context = super(TransactionBaseView, self).get_context_data(**kwargs)
        self.selector = self.kwargs.get('selector', None)
        api_location = reverse('saas_api_transactions')
        if self.selector:
            api_location += '?%s' % urlencode({'selector': self.selector})
        context.update({
            'organization': get_broker(),
            'sort_by_field': 'created_at'})
        update_context_urls(context, {
            'organization': {
                'api_transactions': api_location,
            }
        })
        return context


class AllTransactions(ProviderMixin, TransactionBaseView):

    template_name = 'saas/billing/transactions.html'


class BillingStatementView(OrganizationMixin, TransactionBaseView):
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
      - ``balance_price`` A tuple of the balance amount due by the subscriber
            and unit this balance is expressed in (ex: usd).
      - ``organization`` The subscriber object
      - ``request`` The HTTP request object
    """
    forced_date_range = False
    template_name = 'saas/billing/index.html'

    def get_context_data(self, **kwargs):
        context = super(BillingStatementView, self).get_context_data(**kwargs)
        context.update({
            'organization': self.organization,
            'download_url': reverse(
                'saas_statement_download', kwargs=self.get_url_kwargs())})
        update_context_urls(context,
            {'organization': {
                'api_transactions': reverse(
                    'saas_api_billings', args=(self.organization,)),
                'balance': reverse(
                    'saas_organization_balance', args=(self.organization,)),
                'update_card': reverse(
                    'saas_update_card', args=(self.organization,))}})
        if _valid_manager(self.request, [get_broker()]):
            context['urls']['organization'].update({
                'api_cancel_balance_due': reverse(
                    'saas_api_cancel_balance_due', args=(self.organization,)),
                'vtcharge': reverse('saas_organization_vtcharge',
                    args=(self.organization,))})
        return context


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
        context = super(TransferListView, self).get_context_data(**kwargs)
        context.update({
            'download_url': reverse(
                'saas_transfers_download', kwargs=self.get_url_kwargs())})
        urls = {
            'organization': {
                'api_transactions': reverse(
                'saas_api_transfer_list', args=(self.provider,)),
            },
            'provider': {
                'bank': reverse('saas_update_bank', args=(self.provider,)),
                'import_transactions': reverse(
                    'saas_import_transactions', args=(self.provider,)),
                'withdraw_funds': reverse(
                    'saas_withdraw_funds', args=(self.provider,)),
        }}
        update_context_urls(context, urls)
        return context


class CartBaseView(InvoicablesFormMixin, CartMixin, FormView):
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

        $189.00 Subscription to medium-plan until 2015/11/07 (1 month)
        $510.30 Subscription to medium-plan until 2016/01/07 (3 months, 10% off)
        $907.20 Subscription to medium-plan until 2016/04/07 (6 months, 20% off)
    """

    def dispatch(self, request, *args, **kwargs):
        # We are not getting here without an authenticated user. It is time
        # to store the cart into the database.
        session_cart_to_database(self.request)
        return super(CartBaseView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(CartBaseView, self).get_context_data(**kwargs)
        context.update({'coupon_form': RedeemCouponForm(),
            'submit_title': _("Subscribe")})
        return context

    def get_queryset(self):
        return super(CartBaseView, self).as_invoicables(
            self.request.user, self.organization)

    def get_success_url(self):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return '%s?%s=%s' % (
                reverse('saas_organization_cart', args=(self.organization,)),
                REDIRECT_FIELD_NAME, redirect_path)
        return reverse('saas_organization_cart', args=(self.organization,))


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
            # We use the following convention here:
            # POST parameters prefixed with cart- correspond to an entry
            #    in the invoicables
            plan = invoicable['subscription'].plan
            plan_key = invoicable['name']
            if plan_key in form.cleaned_data:
                selected_line = int(form.cleaned_data[plan_key])
                if (selected_line > 0 and
                    (selected_line - 1) < len(invoicable['options'])):
                    queryset = CartItem.objects.get_cart(
                        user=self.request.user).filter(plan=plan)
                    for cart_item in queryset:
                        cart_item.option = selected_line
                        cart_item.save()

        return super(CartPeriodsView, self).form_valid(form)

    @property
    def cart_items(self):
        if is_authenticated(self.request):
            return CartItem.objects.get_cart(user=self.request.user)
        return CartItem.objects.none()

    def get(self, request, *args, **kwargs):
        if not self.cart_items.exists():
            messages.info(self.request,
              _("Your Cart is empty. Please add some items to your cart before"
" you check out."))
            return http.HttpResponseRedirect(reverse('saas_cart_plan_list'))
        return super(CartPeriodsView, self).get(request, *args, **kwargs)


class CartSeatsView(CartPeriodsView):
    """
    Optional page to subcribe multiple organizations to a ``Plan`` while paying
    through through a third-party ``Organization`` (i.e. self.organization).

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
        if self.cart_items.filter(
                option=0, plan__advance_discount__gt=0).exists():
            # If option == 0 and there is a discount to buy periods
            # in advance, we will present multiple options to the user.
            return http.HttpResponseRedirect(
                reverse('saas_cart_periods', args=(self.organization,)))
        return super(CartSeatsView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(CartSeatsView, self).get_context_data(**kwargs)
        context.update({'is_bulk_buyer': self.organization.is_bulk_buyer})
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
        # Let's first make sure we have valid parameters ...
        params = []
        for item_plan, item_use, item_sync_on in six.moves.zip_longest(
                request.GET.getlist('plan', []),
                request.GET.getlist('use', []),
                request.GET.getlist('sync_on', [])):
            plan = get_object_or_404(Plan, slug=item_plan)
            if item_use:
                use = get_object_or_404(UseCharge, slug=item_use, plan=plan)
            else:
                use = None
            params += [(plan, use, item_sync_on)]
        invoice_key = request.GET.get('invoice_key', None)
        # ... before doing any persistent modifications.
        for item_plan, item_use, item_sync_on in params:
            self.insert_item(request, plan=item_plan, use=item_use,
                sync_on=item_sync_on, invoice_key=invoice_key)
        if (self.organization.is_bulk_buyer and self.cart_items.filter(
                Q(sync_on__isnull=True) | Q(sync_on="")).exists()):
            # A bulk buyer customer can buy subscriptions for other people.
            return http.HttpResponseRedirect(
                reverse('saas_cart_seats', args=(self.organization,)))
        return super(CartView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(CartView, self).get_context_data(**kwargs)
        context.update({'is_bulk_buyer': False})
        return context


class CheckoutView(OrganizationMixin, TemplateView):
    """
    A checkout view
    """

    template_name = 'saas/billing/checkout.html'

    def get_context_data(self, **kwargs):
        context = super(CheckoutView, self).get_context_data(**kwargs)
        context.update({'is_bulk_buyer': self.organization.is_bulk_buyer})
        try:
            context.update(self.organization.retrieve_card())
        except ProcessorConnectionError:
            messages.error(self.request, _("The payment processor is "\
                "currently unreachable. Sorry for the inconvienience."))
        urls = {'organization': {
            'api_checkout': reverse('saas_api_checkout',
                args=(self.organization,)),
             # we don't know charge id yet, so we only fill org
            'receipt': reverse('saas_charge_receipt',
                args=(self.organization, '_')),
            'update_card': reverse('saas_update_card',
                args=(self.organization,))
        }}
        self.update_context_urls(context, urls)
        return context


class VTChargeView(CardFormMixin, FormView):
    """
    Virtual Terminal to create a Charge that is not directly tied to a Plan.
    """

    template_name = 'saas/billing/cart.html'
    organization_url_kwarg = 'customer'
    form_class = VTChargeForm

    def get_context_data(self, **kwargs):
        context = super(VTChargeView, self).get_context_data(**kwargs)
        context.update({'is_extra_charge': True, 'force_update': True})
        return context

    def form_valid(self, form):
        """
        If the form is valid we, optionally, checkout the cart items
        and charge the invoiced items which are due now.
        """
        provider = get_broker() # XXX only works with broker so far.
        # We do not remember the card by default.
        remember_card = False
        if 'remember_card' in self.request.POST:
            remember_card = form.cleaned_data['remember_card']
        processor_token = form.cleaned_data[self.processor_token_id]
        try:
            with transaction.atomic():
                invoiced_item = Transaction.objects.new_payable(
                    self.organization,
                    Price(form.cleaned_data['amount'], settings.DEFAULT_UNIT),
                    provider, form.cleaned_data['descr'])
                invoiced_item.save()
                self.charge = Charge.objects.charge_card(
                    self.organization, [invoiced_item], user=self.request.user,
                    token=processor_token, remember_card=remember_card)
            if self.charge and self.charge.invoiced_total.amount > 0:
                messages.info(self.request, _("A receipt will be sent to"\
" %(email)s once the charge has been processed. Thank you.")
                          % {'email': self.organization.email})
        except ProcessorError as err:
            messages.error(self.request, err)
            return self.form_invalid(form)
        return super(VTChargeView, self).form_valid(form)

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
        return reverse('saas_billing_info', args=(self.organization,))


class ChargeListView(ProviderMixin, TemplateView):
    """
    Display all charges made through a broker.
    """

    template_name = 'saas/billing/charges.html'

    def get_context_data(self, **kwargs):
        context = super(ChargeListView, self).get_context_data(**kwargs)
        urls = {'broker': {
            'api_charges': reverse('saas_api_charges'),
        }}
        update_context_urls(context, urls)
        return context


class ChargeReceiptView(ChargeMixin, ProviderMixin, DetailView):
                        # ``ProviderMixin`` to include menubar urls.
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

    def get_context_data(self, **kwargs):
        context = super(ChargeReceiptView, self).get_context_data(**kwargs)
        for rank, line in enumerate(context['charge_items']):
            event = line.invoiced.get_event()
            setattr(line, 'rank', rank)
            setattr(line, 'refundable',
                event and _valid_manager(self.request, [event.provider]))
        return context


class CouponListView(ProviderMixin, ListView):
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

    def get_context_data(self, **kwargs):
        context = super(CouponListView, self).get_context_data(**kwargs)
        urls_provider = {
            'download_coupons': reverse(
                'saas_metrics_coupons_download', args=(self.provider,))
        }
        if 'urls' in context:
            if 'provider' in context['urls']:
                context['urls']['provider'].update(urls_provider)
            else:
                context['urls'].update({'provider': urls_provider})
        else:
            context.update({'urls': {'provider': urls_provider}})
        return context


class RedeemCouponView(ProviderMixin, FormView):
    """
    Stores a ``Coupon`` into the session for further use in the checkout
    pipeline.
    """
    template_name = 'saas/redeem.html'
    form_class = RedeemCouponForm

    def form_valid(self, form):
        redeemed = Coupon.objects.active(
            self.organization, form.cleaned_data['code']).first()
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
        if is_authenticated(self.request):
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
        invoicables = []
        created_at = datetime_or_now()
        balances = Transaction.objects.get_statement_balances(
            self.organization, until=created_at)
        for event_id in six.iterkeys(balances):
            subscription = Subscription.objects.get_by_event_id(event_id)
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
            organization=self.organization,
            plan__slug=self.kwargs.get(self.plan_url_kwarg))


class WithdrawView(BankMixin, FormView):
    """
    Initiate the transfer of funds from the platform to a provider bank account.

    Template:

    To edit the layout of this page, create a local \
    ``saas/billing/withdraw.html`` (`example <https://github.com/djaodjin/\
djaodjin-saas/tree/master/saas/templates/saas/billing/withdraw.html>`__).

    Template context:
      - ``organization`` The provider object
      - ``request`` The HTTP request object
    """

    form_class = WithdrawForm
    template_name = 'saas/billing/withdraw.html'

    def get_initial(self):
        kwargs = super(WithdrawView, self).get_initial()
        # XXX Remove call to processor backend from a ``View``.
        available_amount = self.provider.retrieve_bank()['balance_amount']
        kwargs.update({
          'unit': "$", # XXX Symbol is currently hardcoded in description.
          'amount': (available_amount / 100.0)
            if (isinstance(available_amount, six.integer_types)
                and available_amount > 0) else 0})
        return kwargs

    def form_valid(self, form):
        amount_withdrawn = int(form.cleaned_data['amount'] * 100)
        self.provider.withdraw_funds(amount_withdrawn, self.request.user)
        return super(WithdrawView, self).form_valid(form)

    def get_success_url(self):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return redirect_path
        return reverse('saas_transfer_info', kwargs=self.get_url_kwargs())

    def get(self, request, *args, **kwargs):
        if not (self.organization.processor_deposit_key
                or is_broker(self.organization)):
            return _insert_url(request, inserted_url=reverse('saas_update_bank',
                args=(self.organization,)))
        return super(WithdrawView, self).get(request, *args, **kwargs)


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
        parts = form.cleaned_data['subscription'].split(Subscription.SEP)
        assert len(parts) == 2
        subscriber = parts[0]
        plan = parts[1]
        subscriber = Organization.objects.filter(slug=subscriber).first()
        if subscriber is None:
            form.add_error(None, _("Invalid subscriber"))
        plan = Plan.objects.filter(
            slug=plan, organization=self.organization).first()
        if plan is None:
            form.add_error(None, _("Invalid plan"))
        subscription = Subscription.objects.active_for(
            organization=subscriber).filter(plan=plan).first()
        if subscription is None:
            form.add_error(None, _("Invalid combination of subscriber and"\
                " plan, or the subscription is no longer active."))
        if form.errors:
            # We haven't found either the subscriber or the plan.
            return self.form_invalid(form)
        Transaction.objects.offline_payment(
            subscription, form.cleaned_data['amount'],
            descr=form.cleaned_data['descr'], user=self.request.user,
            created_at=form.cleaned_data['created_at'])
        return super(ImportTransactionsView, self).form_valid(form)

    def get_success_url(self):
        return reverse('saas_transfer_info', kwargs=self.get_url_kwargs())
