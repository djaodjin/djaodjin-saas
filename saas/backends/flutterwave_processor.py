# Copyright (c) 2024, DjaoDjin inc.
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
Beware the Flutterwave backend is currently experimental!

Install Flutterwave pip package

.. code-block:: shell

    $ pip install rave_python

Go to your `Flutterwave <https://flutterwave.com/>`_ dashboard "API Keys",
then copy/paste the keys into your project settings.py

.. code-block:: python

    SAAS = {
        'PROCESSOR': {
            'BACKEND': 'saas.backends.flutterwave_processor.FlutterwaveBackend',
            'PRIV_KEY': "...",
            'PUB_KEY': "...",
        }
    }

The backend relies on `Flutterwave Inline <https://developer.flutterwave.com/docs/collecting-payments/inline/>`_
such that credit cards numbers are never posted to the application server
running djaodjin-saas (PCI compliance).
"""
import logging

from rave_python import Rave, RaveExceptions

from . import CardError
from .. import settings
from ..compat import six
from ..utils import datetime_or_now, generate_random_slug


LOGGER = logging.getLogger(__name__)


class FlutterwaveBackend(object):

    token_id = 'stripeToken'

    def __init__(self):
        self.pub_key = settings.PROCESSOR.get('PUB_KEY', None)
        self.priv_key = settings.PROCESSOR.get("PRIV_KEY", None)


    def charge_distribution(self, charge,
                            refunded=0, orig_total_broker_fee_amount=0,
                            unit=settings.DEFAULT_UNIT):
        #pylint:disable=unused-argument
        # Stripe processing fee associated to a transaction
        # is 2.9% + 30 cents.
        # Stripe rounds up so we do the same here. Be careful Python 3.x
        # semantics are broken and will return a float instead of a int.
        processor_fee_unit = unit
        available_amount = charge.amount - refunded
        if available_amount > 0:
            # integer division
            processor_fee_amount = (available_amount * 290 + 5000) // 10000 + 30
            assert isinstance(processor_fee_amount, six.integer_types)
        else:
            processor_fee_amount = 0
        distribute_amount = available_amount - processor_fee_amount
        distribute_unit = charge.unit
        broker_fee_amount = 0
        broker_fee_unit = charge.unit
        return (distribute_amount, distribute_unit,
                processor_fee_amount, processor_fee_unit,
                broker_fee_amount, broker_fee_unit)


    def create_payment(self, amount, unit, token,
                       processor_card_key=None,
                       descr=None, stmt_descr=None, created_at=None,
                       broker_fee_amount=0, provider=None, broker=None):
        #pylint: disable=too-many-arguments,unused-argument
        rave = Rave(self.pub_key, self.priv_key,
            usingEnv=False)
        LOGGER.debug(
            "[FlutterwaveBackend.create_payment] create_payment(token=%s)",
            token)
        charge_key = None
        created_at = None
        receipt_info = {}
        try:
            resp = rave.Card.verify(token)
            LOGGER.info(
                "[Flutterwave verification response for '%s': %s",
                token, resp)
            charge_key = resp['flwRef']
            created_at = datetime_or_now(resp['meta'][0]['createdAt'])
            if not resp.transactionComplete:
                raise CardError("Could not complete transaction",
                    resp['chargecode'],
                    charge_processor_key=charge_key)
        except RaveExceptions.TransactionVerificationError as err:
            raise CardError(str(err), err.code,
                charge_processor_key=err.flwRef,
                backend_except=err)

        return (charge_key, created_at, receipt_info)


    def create_transfer(self, provider, amount, unit, descr=None):
        """
        Transfer *amount* into the organization bank account.
        """
        raise NotImplementedError()


    def create_or_update_card(self, subscriber, token,
                              user=None, provider=None, broker=None):
        """
        Create or update a card associated to a subscriber.
        """
        #pylint:disable=too-many-arguments
        raise NotImplementedError()


    def delete_card(self, subscriber, broker=None):
        """
        Removes a card associated to an subscriber.
        """
        raise NotImplementedError()


    def get_payment_context(self, subscriber,
                            amount=None, unit=None, broker_fee_amount=0,
                            provider=None, broker=None):
        #pylint:disable=too-many-arguments,unused-argument
        context = {
            'FLUTTERWAVE_PUB_KEY': self.pub_key,
            'flutterwave_invoice_id': generate_random_slug()
        }
        return context


    def reconcile_transfers(self, provider, created_at, dry_run=False):
        #pylint:disable=unused-argument
        raise NotImplementedError(
            "reconcile_transfers is not implemented on FakeProcessor")



    def refund_charge(self, charge, amount, broker_amount=0):
        """
        Refund a charge on the associated card.
        """
        raise NotImplementedError()



    def retrieve_charge(self, charge):
        if charge.is_progress:
            charge.payment_successful()
        return charge



    def dispute_fee(self, amount): #pylint: disable=unused-argument
        """
        Return processing fee associated to a chargeback (i.e. $15).
        """
        raise NotImplementedError()


    def prorate_transfer(self, amount, provider):
        """
        Return processing fee associated to a transfer (i.e. nothing here).
        """
        #pylint: disable=unused-argument
        raise NotImplementedError()


    def retrieve_card(self, subscriber, broker=None):
        #pylint:disable=unused-argument
        context = {}
        return context
