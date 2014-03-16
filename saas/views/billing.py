# Copyright (c) 2014, Fortylines LLC
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
Views related to billing information
"""

import datetime, logging

from django import forms
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.context_processors import csrf
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.db import IntegrityError
from django.db.models import Q, Sum
from django.db.models.query import QuerySet
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView, FormView, ListView
from django.views.generic.list import MultipleObjectTemplateResponseMixin
from django.views.generic.edit import BaseFormView
from django.views.generic.base import ContextMixin

import saas.backends as backend
import saas.settings as settings
from saas.forms import CreditCardForm, PayNowForm
from saas.views.auth import valid_manager_for_organization
from saas.models import (CartItem, Charge, Coupon, Organization, Plan,
    Transaction, Subscription)
from signup.auth import validate_redirect_url

LOGGER = logging.getLogger(__name__)

def _session_cart_to_database(request):
    """
    Transfer all the items in the cart stored in the session into proper
    records in the database.
    """
    if request.session.has_key('cart_items'):
        for item in request.session['cart_items']:
            plan = Plan.objects.get(slug=item['plan'])
            try:
                CartItem.objects.create(user=request.user, plan=plan)
            except IntegrityError, err:
                # This might happen during testing of the place order
                # through the test driver. Either way, if the item is
                # already in the cart, it is OK to forget about this
                # exception.
                LOGGER.warning('Plan %d is already in %d cart db.',
                               plan.id, request.user.id)
        del request.session['cart_items']


class InsertedURLMixin(ContextMixin):

    def get_context_data(self, **kwargs):
        context = super(InsertedURLMixin, self).get_context_data(**kwargs)
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if not redirect_path:
            redirect_path = validate_redirect_url(
                self.request.META.get('HTTP_REFERER', ''))
        if redirect_path:
            context.update({REDIRECT_FIELD_NAME: redirect_path})
        return context


class InvoicablesMixin(InsertedURLMixin):

    def amounts(self, invoicables):
        total_amount = 0
        for item in invoicables:
            for line in item['lines']:
                if line.dest_account == Transaction.REDEEM:
                    total_amount = total_amount - line.amount
                else:
                    total_amount = total_amount + line.amount
        return total_amount

    def get_invoiced_items(self):
        """
        Returns the transactions which are being charged.
        """
        return []

    def form_valid(self, form):
        """
        If the form is valid we, optionally, checkout the cart items
        and charge the invoiced items which are due now.
        """
        # XXX We always remember the card instead of taking input
        # from the form.cleaned_data['remember_card'] field.
        remember_card = True
        stripe_token = form.cleaned_data['stripeToken']

        if stripe_token and remember_card:
            Organization.objects.associate_processor(
                self.customer, stripe_token)
            stripe_token = None
        # We create a charge based on the transactions created here
        # so we must commit them before creating the charge.
        # This is done indirectly through calling ``get_invoiced_items``.
        self.invoiced_items = self.get_invoiced_items()
        try:
            self.charge = Charge.objects.charge_card(
                self.customer, self.invoiced_items, self.request.user,
                token=stripe_token,
                remember_card=remember_card)
        except Charge.DoesNotExist:
            LOGGER.info('XXX Could not create charge.')
        return super(InvoicablesMixin, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(InvoicablesMixin, self).get_context_data(**kwargs)
        total_amount = self.amounts(self.invoicables)
        context.update({'total_amount': total_amount})
        if total_amount:
            context.update(backend.get_context_data(self.customer))
        return context


class CardFormMixin(object):

    form_class = CreditCardForm
    slug_field = 'name'
    slug_url_kwarg = 'organization'

    def get_object(self, queryset=None):
        return get_object_or_404(
            Organization, slug=self.kwargs.get(self.slug_url_kwarg))

    def get_initial(self):
        """
        Populates place order forms with the organization address
        whenever possible.
        """
        self.customer = self.get_object()
        kwargs = super(CardFormMixin, self).get_initial()
        kwargs.update({'card_name': self.customer.full_name,
                       'card_city': self.customer.locality,
                       'card_address_line1': self.customer.street_address,
                       'card_address_country': self.customer.country_name,
                       'card_address_state': self.customer.region,
                       'card_address_zip': self.customer.postal_code})
        return kwargs


class CardUpdateView(InsertedURLMixin, CardFormMixin, FormView):

    template_name = 'saas/card_update.html'

    def form_valid(self, form):
        now = datetime.datetime.now()
        stripe_token = form.cleaned_data['stripeToken']
        if stripe_token:
            # Since all fields are optional, we cannot assume the card token
            # will be present (i.e. in case of erroneous POST request).
            Organization.objects.associate_processor(
                self.customer, stripe_token)
            email = None
            if self.customer.managers.count() > 0:
                email = self.customer.managers.all()[0].email
                # XXX email all managers that the card was updated.
            messages.success(self.request,
                "Your credit card on file was sucessfully updated")
        return super(CardUpdateView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(CardUpdateView, self).get_context_data(**kwargs)
        context.update(backend.get_context_data(self.customer))
        context.update({'organization': self.customer})
        return context

    def get_success_url(self):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return redirect_path
        return reverse('saas_billing_info', args=(self.customer,))


class TransactionListView(ListView):

    paginate_by = 10
    template_name = 'saas/billing_info.html'

    def get_queryset(self):
        """
        Get the list of transactions for this organization.
        """
        self.customer = get_object_or_404(
            Organization, slug=self.kwargs.get('organization'))
        queryset = Transaction.objects.filter(
            Q(orig_organization=self.customer)
            | Q(dest_organization=self.customer)
        ).order_by('created_at')
        return queryset

    def get_context_data(self, **kwargs):
        context = super(TransactionListView, self).get_context_data(**kwargs)
        # Retrieve customer information from the backend
        context.update({'organization': self.customer})
        balance = Transaction.objects.get_balance(self.customer)
        last4, exp_date = backend.retrieve_card(self.customer)
        context.update({
            'last4': last4,
            'exp_date': exp_date,
            'organization': self.customer,
            'balance_payable': balance
            })
        return context


class PlaceOrderView(InvoicablesMixin, CardFormMixin,
                     MultipleObjectTemplateResponseMixin, BaseFormView):
    """
    Where a user enters his payment information and submit her order.
    """
    template_name = 'saas/place_order.html'

    # Implementation Node:
    #     All fields in CreditCardForm are optional to insure the form
    #     is never invalid and thus allow the same code to place an order
    #     with a total amount of zero.

    def get_invoiced_items(self):
        """
        Returns the transactions which are being charged.
        """
        self.invoicables = self.get_queryset()
        return CartItem.objects.checkout(
            self.invoicables, user=self.request.user)

    def get_queryset(self):
        """
        Get the cart for this customer.
        """
        self.coupons = Coupon.objects.filter(
            user=self.request.user, customer=self.customer, redeemed=False)
        return CartItem.objects.get_invoicables(
            customer=self.customer, user=self.request.user,
            coupons=self.coupons)

    def dispatch(self, *args, **kwargs):
        # We are not getting here without an authenticated user. It is time
        # to store the cart into the database.
        _session_cart_to_database(self.request)
        return super(PlaceOrderView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        self.invoicables = self.get_queryset()
        self.object_list = self.invoicables
        kwargs.update({'object_list': self.object_list})
        context = super(PlaceOrderView, self).get_context_data(**kwargs)
        context.update({'coupons': self.coupons,
                        'coupon_form': RedeemCouponForm(),
                        'organization': self.customer})
        return context

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
        return reverse('saas_organization_profile', args=(self.customer,))


class ChargeReceiptView(DetailView):
    """
    Display a receipt for a created charge.
    """
    model = Charge
    slug_field = 'processor_id'
    slug_url_kwarg = 'charge'
    template_name = 'saas/payment_receipt.html'

    def get_queryset(self):
        """
        Get the cart for this customer.
        """
        queryset = Charge.objects.filter(
            processor_id=self.kwargs.get(self.slug_url_kwarg))
        if queryset.exists():
            self.customer = valid_manager_for_organization(
                self.request.user, queryset.get().customer)
        else:
            raise PermissionDenied
        return queryset

    def get_context_data(self, **kwargs):
        context = super(ChargeReceiptView, self).get_context_data(**kwargs)
        invoiced_items = Transaction.objects.by_charge(self.object)
        context.update({'charge': self.object,
                        'invoiced_items': invoiced_items,
                        'organization': self.customer})
        return context


def pay_now(request, organization):
    organization = get_object_or_404(Organization, slug=organization)
    customer = organization
    context = {'user': request.user, 'organization': organization}
    context.update(csrf(request))
    balance_dues = Transaction.objects.get_balance(customer)
    if balance_dues < 0:
        balance_credits = - balance_dues
        balance_dues = 0
    else:
        balance_credits = None
    if request.method == 'POST':
        form = PayNowForm(request.POST)
        if form.is_valid():
            amount = int(form.cleaned_data['amount'] * 100)
            if form.cleaned_data['full_amount']:
                amount = balance_dues
            if amount > 50:
                # Stripe will not processed charges less than 50 cents.
                last4, exp_date = backend.retrieve_card(customer)
                raise PermissionDenied # XXX until we update to new charge_card method signature.
                charge = Charge.objects.charge_card(
                    customer, amount=amount, user=request.user)
                context.update({
                    'charge_id': charge.pk,
                    'amount': amount,
                    'last4': last4,
                    'exp_date': exp_date})
                return render(request, "saas/payment_receipt.html",
                                          context)
            else:
                messages.error(request,
                    'We do not create charges for less than 50 cents')
        else:
            messages.error(request, 'Unable to create charge')
    else:
        form = PayNowForm()
    context.update({'balance_credits': balance_credits,
                    'balance_dues': balance_dues,
                    'form': form})
    return render(request, "saas/pay_now.html", context)


class RedeemCouponForm(forms.Form):
    """Form used to redeem a coupon."""
    code = forms.CharField(widget=forms.TextInput(
            attrs={'class':'form-control'}))

def redeem_coupon(request, organization):
    """Adds a coupon to the user cart."""
    context = {'user': request.user,
                'organization': organization}
    context.update(csrf(request))
    if request.method == 'POST':
        form = RedeemCouponForm(request.POST)
        if form.is_valid():
            coupon = get_object_or_404(Coupon, code=form.cleaned_data['code'])
            coupon.user = request.user
            coupon.customer = organization
            coupon.save()
        else:
            # XXX on error find a way to get a message back to User.
            pass
    return redirect(reverse('saas_pay_cart', args=(organization,)))


class PaySubscriptionView(InvoicablesMixin, CardFormMixin, FormView):
    """
    Create a charge for a ``Subscription``.
    """

    plan_url_kwarg = 'subscribed_plan'
    template_name = 'saas/pay_subscription.html'

    def get_invoiced_items(self):
        """
        Returns the transactions which are being charged.
        """
        self.subscription = self.get_subscription()
        invoicables = Transaction.objects.get_invoicables(
            self.subscription)
        invoiced_items = Transaction.objects.none()
        for invoicable in invoicables:
            # Because we added a "fake" balance Transaction.
            if isinstance(invoicable['lines'], QuerySet):
                invoiced_items |= invoicable['lines']
        return invoiced_items

    def get_subscription(self):
        return get_object_or_404(Subscription,
            organization__slug=self.kwargs.get('organization'),
            plan__slug=self.kwargs.get(self.plan_url_kwarg))

    def get_context_data(self, **kwargs):
        self.subscription = self.get_subscription()
        self.invoicables = Transaction.objects.get_invoicables(
            self.subscription)
        context = super(PaySubscriptionView, self).get_context_data(**kwargs)
        last_charge = Charge.objects.last_charge(self.subscription)
        if (not last_charge
            or last_charge.state == Charge.FAILED
            or last_charge.state == Charge.DISPUTED):
            # No charge yet, let's run it. First, get the balance items
            # charge failed does not hurt to show again balance.
            pass
        context.update({'subscription': self.subscription,
                        'last_charge': last_charge,
                        'object_list': self.invoicables,
                        'organization': self.customer})
        return context

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
        return reverse('saas_organization_profile', args=(self.customer,))
