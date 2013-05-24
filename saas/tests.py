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

import datetime, time, urlparse
from unittest import skip

from django.test import TestCase
from django.test.client import Client
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from saas.models import Organization, Transaction, Charge
from saas.ledger import balance, read_balances
from saas.charge import (
    charge_succeeded,
    charge_failed,
    charge_refunded,
    charge_captured,
    charge_dispute_created,
    charge_dispute_updated,
    charge_dispute_closed,
    create_charges)


#@skip("debugging")
class LedgerTests(TestCase):
    '''Tests ledger functionality.'''
    fixtures = ['test_data']

    @classmethod
    def setUpClass(cls):
        cls.firstTime = True

    def setUp(self):
        if LedgerTests.firstTime:
            # Implementation Node:
            # It seems the fixture is only loaded after setUpClass was called.
            for customer_id, amount in read_balances():
                # Make sure all organizations have a valid procesor_id
                # and associated credit card.
                #print "XXX %s balance of %dc" %(customer_id, amount)
                Organization.objects.associate_processor(
                    customer_id, card={'number': '4242424242424242',
                                    'exp_month': '12',
                                    'exp_year': '2014'})
            LedgerTests.firstTime = False

    def _create_charge(self, customer_name, amount):
        customer = Organization.objects.get(name=customer_name)
        charge = Charge.objects.charge_card(
            customer, amount=1000)
        return customer, charge.processor_id

    def _create_charge_for_balance(self, customer_name):
        customer = Organization.objects.get(name=customer_name)
        prev_balance = balance(customer)
        charge = Charge.objects.charge_card(
            customer, amount=prev_balance)
        return customer, charge.processor_id

    def test_create_usage(self):
        customer, processor_id = self._create_charge('ABC', 1000)
        assert len(processor_id) > 0

    def test_pay_now(self):
        """Pay the balance of account.
        No Issue."""
        customer, charge_id = self._create_charge_for_balance('ABC')
        charge_succeeded(charge_id)
        next_balance = balance(customer)
        assert(next_balance == 0)

    def test_pay_now_two_success(self):
        """Pay the balance of account.
        Receive two 'charge.succeeded' events."""
        customer, charge_id = self._create_charge_for_balance('ABC')
        charge_succeeded(charge_id)
        charge_succeeded(charge_id)
        next_balance = balance(customer)
        assert(next_balance == 0)


    def test_charge_cards(self):
        """Charge all customers credit cards for fees due
        since the last time the card was charged."""
        create_charges(until=datetime.datetime(2013, 04, 21))
        assert True
