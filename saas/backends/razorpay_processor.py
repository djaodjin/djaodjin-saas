# Copyright (c) 2021, DjaoDjin inc.
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
Install Razorpay pip package

.. code-block:: shell

    $ pip install razorpay

Go to your `Razorpay <https://razorpay.com/>`_ dashboard "API Keys",
click on "Generate Key", then copy/paste the keys into your project settings.py

.. code-block:: python

    SAAS = {
        'PROCESSOR': {
            'BACKEND': 'saas.backends.razorpay_processor.RazorpayBackend',
            'PRIV_KEY': "...",
            'PUB_KEY': "...",
        }
    }
"""

import datetime, logging

import razorpay, razorpay.errors

from .. import settings
from ..utils import utctimestamp_to_datetime
from . import CardError, ProcessorError


LOGGER = logging.getLogger(__name__)


class RazorpayBackend(object):

    bypass_api = False
    token_id = 'razorpay_payment_id'

    def __init__(self):
        self.pub_key = settings.PROCESSOR['PUB_KEY']
        self.priv_key = settings.PROCESSOR['PRIV_KEY']
        self.razor = razorpay.Client(auth=(self.pub_key, self.priv_key))

    def charge_distribution(self, charge, refunded=0, unit='inr'):
        if self.bypass_api:
            processor_charge = {
                'fee': 0, 'service_tax': 0, 'amount': charge.amount}
        else:
            processor_charge = self.razor.payment.fetch(charge.processor_key)
        processor_fee_amount = (
            processor_charge['fee'] + processor_charge['service_tax'])
        processor_fee_unit = unit
        distribute_amount = processor_charge['amount'] - processor_fee_amount
        distribute_unit = unit
        LOGGER.debug("charge_distribution(charge=%s, amount=%d %s)"\
            "distribute: %d %s, fee: %d %s",
            charge.processor_key, refunded, unit,
            distribute_amount, distribute_unit,
            processor_fee_amount, processor_fee_unit)
        broker_fee_amount = 0
        broker_fee_unit = charge.unit
        return (distribute_amount, distribute_unit,
                processor_fee_amount, processor_fee_unit,
                broker_fee_amount, broker_fee_unit)

    def create_payment(self, amount, unit, provider,
                       processor_card_key=None, token=None,
                       descr=None, stmt_descr=None, created_at=None,
                       broker_fee_amount=0):
        #pylint: disable=too-many-arguments,unused-argument
        LOGGER.debug('create_payment(amount=%s, unit=%s, descr=%s)',
            amount, unit, descr)
        try:
            processor_charge = self.razor.payment.capture(token, amount)
        except razorpay.errors.RazorpayError as err:
            raise CardError(err.error, "unknown", backend_except=err)
        LOGGER.info('capture %s', processor_charge,
            extra={'event': 'capture', 'processor': 'razorpay',
                'processor_key': processor_charge['id']})
        created_at = utctimestamp_to_datetime(processor_charge['created_at'])
        exp_year = created_at.year
        exp_month = created_at.month
        receipt_info = {
            'last4': 0, 'exp_date': datetime.date(exp_year, exp_month, 1),
            'card_name': ""}
        return (processor_charge['id'], created_at, receipt_info)

    def delete_card(self, subscriber, broker=None):
        """
        Removes a card associated to an subscriber.
        """
        raise NotImplementedError()

    def get_deposit_context(self):
        context = {
            'RAZORPAY_PUB_KEY': self.pub_key
        }
        return context

    def get_payment_context(self, provider, processor_card_key,
                            amount=None, unit=None, broker_fee_amount=0,
                            subscriber_email=None, subscriber_slug=None):
        #pylint:disable=too-many-arguments,unused-argument
        context = {
            'RAZORPAY_PUB_KEY': self.pub_key
        }
        return context

    @staticmethod
    def reconcile_transfers(provider, created_at, dry_run=False):
        #pylint:disable=unused-argument
        LOGGER.warning("There are no RazorPay APIs to implement this method.")

    def retrieve_bank(self, provider):
        #pylint:disable=unused-argument
        return self.get_deposit_context()

    def retrieve_card(self, subscriber, broker=None):
        #pylint:disable=unused-argument,no-self-use
        context = {}
        return context

    def retrieve_charge(self, charge):
        if charge.is_progress:
            processor_charge = self.razor.payment.fetch(charge.processor_key)
            if processor_charge['status'] == 'captured':
                charge.payment_successful()
        return charge

    def refund_charge(self, charge, amount, broker_amount=0):
        """
        Full or partial refund a charge.
        """
        try:
            self.razor.refund.create(
                charge.processor_key, data={"amount": amount})
            processor_charge = self.razor.payment.fetch(charge.processor_key)
            LOGGER.debug('refund %d inr %s', amount, processor_charge)
        except razorpay.errors.RazorpayError as err:
            raise ProcessorError(err.error, backend_except=err)

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
