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

import datetime, logging

from ..utils import datetime_or_now, generate_random_slug


LOGGER = logging.getLogger(__name__)


class FakeProcessorBackend(object):

    @staticmethod
    def charge_distribution(charge, refunded=0, unit='usd'):
        # Stripe processing fee associated to a transaction
        # is 2.9% + 30 cents.
        # Stripe rounds up so we do the same here. Be careful Python 3.x
        # semantics are broken and will return a float instead of a int.
        fee_unit = unit
        available_amount = charge.amount - refunded
        if available_amount > 0:
            fee_amount = (available_amount * 290 + 5000) / 10000 + 30
        else:
            fee_amount = 0
        distribute_amount = available_amount - fee_amount
        distribute_unit = charge.unit
        return distribute_amount, distribute_unit, fee_amount, fee_unit

    @staticmethod
    def create_charge(customer, amount, unit,
                    broker=None, descr=None, stmt_descr=None):
        #pylint: disable=too-many-arguments,unused-argument
        LOGGER.debug('create_charge(amount=%s, unit=%s, descr=%s)',
            amount, unit, descr)
        created_at = datetime_or_now()
        return (generate_random_slug(), created_at,
            '1234', created_at + datetime.timedelta(days=365))

    @staticmethod
    def create_charge_on_card(card, amount, unit,
                    broker=None, descr=None, stmt_descr=None):
        #pylint: disable=too-many-arguments,unused-argument
        LOGGER.debug('create_charge_on_card(amount=%s, unit=%s, descr=%s)',
            amount, unit, descr)
        created_at = datetime_or_now()
        return (generate_random_slug(), created_at,
            '1234', created_at + datetime.timedelta(days=365))

    @staticmethod
    def create_transfer(provider, amount, unit, descr=None):
        """
        Transfer *amount* into the organization bank account.
        """
        LOGGER.debug(
            "create_transfer(provider=%s, amount=%s, unit=%s, descr=%s)",
            provider, amount, unit, descr)
        created_at = datetime_or_now()
        return (generate_random_slug(), created_at)

    @staticmethod
    def refund_charge(charge, amount):
        """
        Refund a charge on the associated card.
        """
        pass

    @staticmethod
    def dispute_fee(amount): #pylint: disable=unused-argument
        """
        Return processing fee associated to a chargeback (i.e. $15).
        """
        return 1500

    @staticmethod
    def prorate_transfer(amount, provider): #pylint: disable=unused-argument
        """
        Return processing fee associated to a transfer (i.e. nothing here).
        """
        return 0
