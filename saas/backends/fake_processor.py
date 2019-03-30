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

import datetime, logging

from django.utils import six

from ..utils import datetime_or_now, generate_random_slug
from .. import settings


LOGGER = logging.getLogger(__name__)


class FakeProcessorBackend(object):

    LOCAL = 0
    FORWARD = 1
    REMOTE = 2

    token_id = 'stripeToken'

    def __init__(self):
        self.pub_key = settings.PROCESSOR['PUB_KEY']
        self.priv_key = settings.PROCESSOR['PRIV_KEY']
        self.client_id = settings.PROCESSOR.get('CLIENT_ID', None)
        self.mode = settings.PROCESSOR.get('MODE', 0)

    @staticmethod
    def charge_distribution(charge, refunded=0, unit=settings.DEFAULT_UNIT):
        # Stripe processing fee associated to a transaction
        # is 2.9% + 30 cents.
        # Stripe rounds up so we do the same here. Be careful Python 3.x
        # semantics are broken and will return a float instead of a int.
        fee_unit = unit
        available_amount = charge.amount - refunded
        if available_amount > 0:
            # integer division
            fee_amount = (available_amount * 290 + 5000) // 10000 + 30
            assert isinstance(fee_amount, six.integer_types)
        else:
            fee_amount = 0
        distribute_amount = available_amount - fee_amount
        distribute_unit = charge.unit
        return distribute_amount, distribute_unit, fee_amount, fee_unit

    @staticmethod
    def create_charge(customer, amount, unit,
                    broker=None, descr=None, stmt_descr=None, created_at=None):
        #pylint: disable=too-many-arguments,unused-argument
        created_at = datetime_or_now(created_at)
        receipt_info = {
            'last4': "1234",
            'exp_date': created_at + datetime.timedelta(days=365),
            'card_name': "Joe Test"
        }
        charge_key = "fake_%s" % generate_random_slug()
        LOGGER.debug("create_charge(amount=%s, unit='%s', descr='%s') => %s",
            amount, unit, descr, charge_key)
        return (charge_key, created_at, receipt_info)

    def create_charge_on_card(self, card, amount, unit,
                    broker=None, descr=None, stmt_descr=None, created_at=None):
        #pylint: disable=too-many-arguments,unused-argument
        return self.create_charge(card, amount, unit,
                    broker=broker, descr=descr,
                    stmt_descr=descr, created_at=created_at)

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

    def delete_card(self, subscriber, broker=None):
        """
        Removes a card associated to an subscriber.
        """
        pass

    @staticmethod
    def reconcile_transfers(provider, created_at, dry_run=False):
        #pylint:disable=unused-argument
        raise NotImplementedError(
            "reconcile_transfers is not implemented on FakeProcessor")

    @staticmethod
    def refund_charge(charge, amount):
        """
        Refund a charge on the associated card.
        """
        pass

    @staticmethod
    def retrieve_charge(charge):
        if charge.is_progress:
            charge.payment_successful()
        return charge

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
