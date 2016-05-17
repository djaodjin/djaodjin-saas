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

    token_id = 'razorpay_payment_id'

    def __init__(self):
        self.pub_key = settings.PROCESSOR['PUB_KEY']
        self.priv_key = settings.PROCESSOR['PRIV_KEY']
        self.razor = razorpay.Client(auth=(self.pub_key, self.priv_key))

    def charge_distribution(self, charge, refunded=0, unit='inr'):
        processor_charge = self.razor.payment.fetch(charge.processor_key)
        fee_amount = processor_charge['fee'] + processor_charge['service_tax']
        fee_unit = unit
        distribute_amount = processor_charge['amount'] - fee_amount
        distribute_unit = unit
        LOGGER.debug("charge_distribution(charge=%s, amount=%d %s)"\
            "distribute: %d %s, fee: %d %s",
            charge.processor_key, refunded, unit,
            distribute_amount, distribute_unit,
            fee_amount, fee_unit)
        return distribute_amount, distribute_unit, fee_amount, fee_unit

    def create_charge(self, customer, amount, unit,
                    broker=None, descr=None, stmt_descr=None):
        #pylint: disable=too-many-arguments,unused-argument
        """
        Create a charge on the default card associated to the customer.

        This method is not implemented as Razorpay does not allow
        to create a charge on a stored credit card.
        """
        raise NotImplementedError()

    def create_charge_on_card(self, card, amount, unit,
                    broker=None, descr=None, stmt_descr=None):
        #pylint: disable=too-many-arguments,unused-argument
        LOGGER.debug('create_charge_on_card(amount=%s, unit=%s, descr=%s)',
            amount, unit, descr)
        try:
            processor_charge = self.razor.payment.capture(card, amount)
        except razorpay.errors.RazorpayError, err:
            raise CardError(err.error, "unknown", backend_except=err)
        LOGGER.info('capture %s', processor_charge)
        created_at = utctimestamp_to_datetime(processor_charge['created_at'])
        last4 = 0
        exp_year = created_at.year
        exp_month = created_at.month
        return (processor_charge['id'], created_at, last4,
                datetime.date(exp_year, exp_month, 1))

    def retrieve_card(self, subscriber, broker=None):
        #pylint:disable=unused-argument
        context = {'RAZORPAY_PUB_KEY': self.pub_key}
        return context

    def retrieve_charge(self, charge):
        if charge.is_progress:
            processor_charge = self.razor.payment.fetch(charge.processor_key)
            if processor_charge['status'] == 'captured':
                charge.payment_successful()
        return charge

    def refund_charge(self, charge, amount):
        """
        Full or partial refund a charge.
        """
        try:
            self.razor.refund.create(
                charge.processor_key, data={"amount": amount})
            processor_charge = self.razor.payment.fetch(charge.processor_key)
            LOGGER.info('refund %d inr %s', amount, processor_charge)
        except razorpay.errors.RazorpayError, err:
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
