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
Dealing with charges
"""

import logging

from django.db.models import Sum

from saas.compat import datetime_or_now
from saas.models import Charge, Organization, Transaction


LOGGER = logging.getLogger(__name__)


def create_charges_for_balance(until=None):
    """
    Create charges for all accounts payable.
    """
    until = datetime_or_now(until)
    for organization in Organization.objects.all():
        charges = Charge.objects.filter(customer=organization).exclude(
            state=Charge.DONE).aggregate(Sum('amount'))
        inflight_charges = charges['amount__sum']
        # We will create charges only when we have no charges
        # already in flight for this customer.
        if not inflight_charges:
            balance_t = Transaction.objects.get_organization_payable(
                organization, until=until)
            if balance_t.dest_amount > 50:
                LOGGER.info('CHARGE %dc to %s',
                    balance_t.dest_amount, balance_t.dest_organization)
                # Stripe will not processed charges less than 50 cents.
                try:
                    balance_t.save()
                    Charge.objects.charge_card(
                        balance_t.dest_organization, balance_t)
                except:
                    raise
            else:
                LOGGER.info('SKIP   %s (less than 50c)',
                    balance_t.dest_organization)
        else:
            LOGGER.info('SKIP   %s (one charge already in flight)',
                balance_t.dest_organization)
