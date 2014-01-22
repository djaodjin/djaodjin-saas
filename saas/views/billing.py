# Copyright (c) 2013, The DjaoDjin Team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Manage Billing information"""

import datetime, logging

from django import forms
from django.db.models import Q, Sum
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
from django.core.context_processors import csrf
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_GET
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import BaseFormView
from django.utils.decorators import method_decorator
from django.shortcuts import render, redirect, get_object_or_404

import saas.backends as backend
import saas.settings as settings
from saas.ledger import balance
from saas.forms import CreditCardForm, PayNowForm
from saas.views.auth import managed_organizations, valid_manager_for_organization
from saas.models import Organization, Transaction, Charge, CartItem, Coupon


LOGGER = logging.getLogger(__name__)


class TransactionListView(ListView):

    paginate_by = 10
    template_name = 'saas/billing_info.html'

    def get_queryset(self):
        """
        Get the list of transactions for this organization.
        """
        queryset = Transaction.objects.filter(
            Q(orig_organization=self.customer)
            | Q(dest_organization=self.customer)
        ).order_by('created_at')
        return queryset

    def dispatch(self, *args, **kwargs):
        self.customer = kwargs.get('organization')
        return super(TransactionListView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(TransactionListView, self).get_context_data(**kwargs)
        # Retrieve customer information from the backend
        context.update({'organization': self.customer})
        last4, exp_date = backend.retrieve_card(self.customer)
        context.update({
            'last4': last4,
            'exp_date': exp_date,
            'organization': self.customer
            })
        return context


class PlaceOrderView(BaseFormView, ListView):
    """
    Where a user enters his payment information and submit her order.
    """
    template_name = 'saas/place_order.html'
    form_class = CreditCardForm

    # Implementation Node:
    #     All fields in CreditCardForm are optional to insure the form
    #     is never invalid and thus allow the same code to place an order
    #     with a total amount of zero.

    def form_valid(self, form):
        """
        If the form is valid, a Charge was created on Stripe,
        we just have to add one Transaction per new subscription
        as well as associate that subscription to the appropriate
        organization.
        """
        cart = CartItem.objects.get_cart(
            customer=self.customer, user=self.request.user)
        coupons = Coupon.objects.filter(
            user=self.request.user, customer=self.customer, redeemed=False)
        total_amount, discount_amount = self.amounts(
            self.get_invoicables(), coupons)
        if total_amount:
            self.charge = Charge.objects.charge_card(
                self.customer, total_amount, self.request.user,
                token=form.cleaned_data['stripeToken'],
                remember_card=form.cleaned_data['remember_card'])
        # We commit in the db AFTER the charge goes through. In case anything
        # goes wrong with the charge the cart is still in a consistent state.
        Transaction.objects.subscribe_to(cart)
        if len(coupons) > 0:
            Transaction.objects.redeem_coupon(discount_amount, coupons[0])
        return super(PlaceOrderView, self).form_valid(form)

    def get_success_url(self):
        if hasattr(self, 'charge'):
            return reverse('saas_charge_receipt',
                           args=(self.customer, self.charge.processor_id))
        messages.info(self.request,
                      _("Your order has been processed. Thank you!"))
        return reverse('saas_organization_profile', args=(self.customer,))

    def amounts(self, cart, coupons):
        discount_amount = 0
        total_amount = 0
        for item in cart:
            total_amount = total_amount + item["amount"]
        # Reduce price by as much  Coupon.
        if len(coupons) > 0:
            discount_amount = total_amount
        return total_amount - discount_amount, discount_amount

    def get_invoicables(self):
        """
        Get the cart for this customer.
        """
        return CartItem.objects.get_invoicables(
            customer=self.customer, user=self.request.user)

    def get_queryset(self):
        """
        Get the cart for this customer.
        """
        queryset = self.get_invoicables()
        return queryset

    def dispatch(self, *args, **kwargs):
        organization = kwargs.get('organization')
        if not organization:
            organizations = managed_organizations(self.request.user)
            if len(organizations) == 1:
                organization = organizations[0]
        self.customer = valid_manager_for_organization(
            self.request.user, organization)
        return super(PlaceOrderView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        if not 'object_list' in kwargs:
            cart = self.get_queryset()
            kwargs.update({'object_list': cart})
        context = super(PlaceOrderView, self).get_context_data(**kwargs)
        # Reduce price by as much  Coupon.
        coupons = Coupon.objects.filter(
            user=self.request.user, customer=self.customer, redeemed=False)
        total_amount, discount_amount = self.amounts(self.object_list, coupons)
        context.update({'coupons': coupons,
                        'discount_amount': discount_amount,
                        'coupon_form': RedeemCouponForm(),
                        'total_amount': total_amount,
                        'organization': self.customer})
        if total_amount:
            context.update({'STRIPE_PUB_KEY': settings.STRIPE_PUB_KEY})
            # Retrieve customer information from the backend
            last4, exp_date = backend.retrieve_card(self.customer)
            if last4 != "N/A":
                context.update({'last4': last4, 'exp_date': exp_date})
        return context


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
        context.update({'last4': self.object.last4,
                        'exp_date': self.object.exp_date,
                        'charge_id': self.object.processor_id,
                        'amount': self.object.amount,
                        'organization': Organization.objects.get_site_owner()})
        return context


def pay_now(request, organization):
    context = { 'user': request.user,
                'organization': organization }
    context.update(csrf(request))
    balance_dues = balance(customer)
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
            messages.error(request,'Unable to create charge')
    else:
        form = PayNowForm()
    context.update({'balance_credits': balance_credits,
                    'balance_dues': balance_dues,
                    'form': form})
    return render(request, "saas/pay_now.html", context)


class RedeemCouponForm(forms.Form):
    """Form used to redeem a coupon."""
    code = forms.CharField(widget=forms.TextInput(attrs={'class':'form-control'}))

def redeem_coupon(request, organization):
    """Adds a coupon to the user cart."""
    context = { 'user': request.user,
                'organization': organization }
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
    return redirect(reverse('saas_pay_cart', args=(organization.name,)))


def update_card(request, organization):
    context = { 'user': request.user,
                'organization': organization }
    context.update(csrf(request))
    if request.method == 'POST':
        form = CreditCardForm(request.POST)
        if form.is_valid():
            now = datetime.datetime.now()
            stripe_token = form.cleaned_data['stripeToken']
            # With Stripe, we don't need to wait on an IPN. We get
            # a card token here.
            Organization.objects.associate_processor(organization, stripe_token)
            email = None
            if organization.managers.count() > 0:
                email = organization.managers.all()[0].email
            messages.success(request,
                "Your credit card on file was sucessfully updated")
            return redirect(reverse('saas_billing_info',
                                    args=(organization.name,)))
        else:
            messages.error(request, "The form did not validates")
    else:
        form = CreditCardForm()
    context.update({'form': form})
    context.update({ 'STRIPE_PUB_KEY': settings.STRIPE_PUB_KEY })
    return render(request, "saas/card_update.html", context)
