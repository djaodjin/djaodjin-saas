# Copyright (c) 2013, Fortylines LLC
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

from django.db.models import Q
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.core.context_processors import csrf
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET

import saas.settings as settings
from saas.ledger import balance
from saas.forms import CreditCardForm, PayNowForm
from saas.models import Organization
from saas.models import Transaction, Charge
from saas.views.auth import valid_manager_for_organization
import saas.backends as backend
from saas.decorators import requires_agreement

LOGGER = logging.getLogger(__name__)


@require_GET
@requires_agreement('terms_of_use')
def billing_info(request, organization_id):
    context = { 'user': request.user }
    context.update(csrf(request))
    customer = valid_manager_for_organization(request.user, organization_id)
    context.update({'organization': customer })
    # Retrieve customer information from the backend
    last4, exp_date = backend.retrieve_card(customer)
    # Retrieve latest transactions
    period_end = datetime.datetime.now() - datetime.timedelta(days=31)
    transactions = Transaction.objects.filter(
        Q(orig_organization=customer) | Q(dest_organization=customer)
        ).order_by('created_at')[:25]
    context.update({
            'last4': last4,
            'exp_date': exp_date,
            'transactions': transactions,
            })
    return render(request, "saas/billing_info.html", context)


@requires_agreement('terms_of_use')
def pay_now(request, organization_id):
    context = { 'user': request.user }
    context.update(csrf(request))
    customer = valid_manager_for_organization(request.user, organization_id)
    context.update({'organization': customer })
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


@requires_agreement('terms_of_use')
def update_card(request, organization_id):
    context = { 'user': request.user }
    context.update(csrf(request))
    customer = valid_manager_for_organization(request.user, organization_id)
    context.update({ 'organization': customer })
    if request.method == 'POST':
        form = CreditCardForm(request.POST)
        if form.is_valid():
            now = datetime.datetime.now()
            stripe_token = form.cleaned_data['stripeToken']
            # With Stripe, we don't need to wait on an IPN. We get
            # a card token here.
            Organization.objects.associate_processor(customer, stripe_token)
            email = None
            if customer.managers.count() > 0:
                email = customer.managers.all()[0].email
            messages.success(request,
                "Your credit card on file was sucessfully updated")
            return redirect(reverse('saas_billing_info', args=(customer.name,)))
        else:
            messages.error(request, "The form did not validates")
    else:
        form = CreditCardForm()
    context.update({'form': form})
    context.update({ 'STRIPE_PUB_KEY': settings.STRIPE_PUB_KEY })
    return render(request, "saas/update_card.html", context)
