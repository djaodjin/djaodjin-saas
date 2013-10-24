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

"""Dealing with charges"""

import datetime, logging

from django.db.models import Sum
from django.shortcuts import get_object_or_404

from saas.models import Organization, Charge, Transaction
from saas.ledger import read_balances

LOGGER = logging.getLogger(__name__)

def create_charges(until=datetime.datetime.now()):
    """Create a set of charges based on the transaction table."""

    for customer_id, balance in read_balances(until):
        customer = Organization.objects.get(pk=customer_id)
        charges = Charge.objects.filter(customer=customer).exclude(
            state=Charge.DONE).aggregate(Sum('amount'))
        inflight_charges = charges['amount__sum']
        # We will create charges only when we have no charges
        # already in flight for this customer.
        if not inflight_charges:
            inflight_charges = 0 # Such that subsequent logic works regardless
            amount = balance - inflight_charges
            if amount > 50:
                LOGGER.info('CHARGE %dc to %s', amount, customer.name)
                # Stripe will not processed charges less than 50 cents.
                try:
                    charge = Charge.objects.charge_card(customer, amount=amount)
                except:
                    raise
            else:
                LOGGER.info('SKIP   %s (less than 50c)',
                            customer.name)
        else:
            LOGGER.info('SKIP   %s (one charge already in flight)',
                            customer.name)


def charge_succeeded(charge_id):
    """Invoked by the processor callback when a charge has succeeded."""
    charge = get_object_or_404(Charge, processor_id=charge_id)
    if charge.state != charge.DONE:
        charge.state = charge.DONE
        charge.save()
        Transaction.objects.pay_balance(
            charge.customer, charge.amount,
            description=charge.description,
            event_id=charge.id)

def charge_failed(charge_id):
    """Invoked by the processor callback when a charge has failed."""
    charge = get_object_or_404(Charge, processor_id=charge_id)
    charge.state = charge.FAILED
    charge.save()

def charge_refunded(charge_id):
    """Invoked by the processor callback when a charge has been refunded."""
    charge = get_object_or_404(Charge, processor_id=charge_id)

def charge_captured(charge_id):
    charge = get_object_or_404(Charge, processor_id=charge_id)

def charge_dispute_created(charge_id):
    """Invoked by the processor callback when a charge has been disputed."""
    charge = get_object_or_404(Charge, processor_id=charge_id)
    charge.state = charge.DISPUTED
    charge.save()

def charge_dispute_updated(charge_id):
    """Invoked by the processor callback when a disputed charge has been
    updated."""
    charge = get_object_or_404(Charge, processor_id=charge_id)

def charge_dispute_closed(charge_id):
    """Invoked by the processor callback when a disputed charge has been
    closed."""
    charge = get_object_or_404(Charge, processor_id=charge_id)
    charge.state = charge.DONE
    charge.save()


