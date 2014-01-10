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

import time, urlparse
from datetime import date, datetime
from unittest import skip

from django.test import TestCase
from django.utils.timezone import utc
from django.test.client import Client
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.core.management import call_command
from django.db import transaction

from saas.views.metrics import (month_periods,
                                organization_monthly_revenue_customers)
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


@skip("still pb committing the associated processor_id before the tests start")
class LedgerTests(TestCase):
    '''Tests ledger functionality.'''
    fixtures = [ 'test_data' ]

    @classmethod
    def setUpClass(cls):
        # Transactions are discarded and fixtures reloaded after
        # each test case so we have to insure all organizations
        # have a valid procesor_id and associated credit card.

        # We have to use this slightly awkward syntax due to the fact
        # that we're using *args and **kwargs together.
        call_command('loaddata', *['test_organization'],
                     **{'verbosity': 0, 'database': 'default',
                        'skip_validation': True})

        transaction.commit_unless_managed(using='default')
        transaction.enter_transaction_management(using='default')
        transaction.managed(True, using='default')
        for customer in Organization.objects.all():
            Organization.objects.associate_processor(
                customer, card={'number': '4242424242424242',
                                'exp_month': '12',
                                'exp_year': '2014'})
        transaction.commit(using='default')
        transaction.leave_transaction_management(using='default')

    def _create_charge(self, customer_name, amount):
        customer = Organization.objects.get(name=customer_name)
        customer = Organization.objects.get(name=customer_name)
        charge = Charge.objects.charge_card(
            customer, amount=amount)
        return customer, charge.processor_id

    def _create_charge_for_balance(self, customer_name):
        customer = Organization.objects.get(name=customer_name)
        prev_balance = balance(customer)
        charge = Charge.objects.charge_card(
            customer, amount=prev_balance)
        return customer, charge.processor_id

    def test_create_usage(self):
        customer, processor_id = self._create_charge('abc', 1000)
        assert len(processor_id) > 0

    def test_pay_now(self):
        """Pay the balance of account.
        No Issue."""
        customer, charge_id = self._create_charge_for_balance('abc')
        charge_succeeded(charge_id)
        next_balance = balance(customer)
        assert(next_balance == 0)

    def test_pay_now_two_success(self):
        """Pay the balance of account.
        Receive two 'charge.succeeded' events."""
        customer, charge_id = self._create_charge_for_balance('abc')
        charge_succeeded(charge_id)
        charge_succeeded(charge_id)
        next_balance = balance(customer)
        assert(next_balance == 0)

    def test_charge_cards(self):
        """Charge all customers credit cards for fees due
        since the last time the card was charged."""
        create_charges(until=datetime(2013, 04, 21))
        assert True


#@skip("debugging")
class MetricsTests(TestCase):
    '''Tests ledger functionality.'''
    fixtures = ['test_organization', 'test_metrics']

    def test_month_periods_full_year(self):
        dates = month_periods(
            from_date=date(year=2014, month=1, day=1))
        assert len(dates) == 13
        assert dates[0] == datetime(year=2013, month=1, day=1, tzinfo=utc)
        assert dates[1] == datetime(year=2013, month=2, day=1, tzinfo=utc)
        assert dates[2] == datetime(year=2013, month=3, day=1, tzinfo=utc)
        assert dates[3] == datetime(year=2013, month=4, day=1, tzinfo=utc)
        assert dates[4] == datetime(year=2013, month=5, day=1, tzinfo=utc)
        assert dates[5] == datetime(year=2013, month=6, day=1, tzinfo=utc)
        assert dates[6] == datetime(year=2013, month=7, day=1, tzinfo=utc)
        assert dates[7] == datetime(year=2013, month=8, day=1, tzinfo=utc)
        assert dates[8] == datetime(year=2013, month=9, day=1, tzinfo=utc)
        assert dates[9] == datetime(year=2013, month=10, day=1, tzinfo=utc)
        assert dates[10] == datetime(year=2013, month=11, day=1, tzinfo=utc)
        assert dates[11] == datetime(year=2013, month=12, day=1, tzinfo=utc)
        assert dates[12] == datetime(year=2014, month=1, day=1, tzinfo=utc)

    def test_month_periods_incomplete_last_month(self):
        dates = month_periods(
            from_date=date(year=2014, month=1, day=9))
        assert len(dates) == 13
        assert dates[0] == datetime(year=2013, month=2, day=1, tzinfo=utc)
        assert dates[1] == datetime(year=2013, month=3, day=1, tzinfo=utc)
        assert dates[2] == datetime(year=2013, month=4, day=1, tzinfo=utc)
        assert dates[3] == datetime(year=2013, month=5, day=1, tzinfo=utc)
        assert dates[4] == datetime(year=2013, month=6, day=1, tzinfo=utc)
        assert dates[5] == datetime(year=2013, month=7, day=1, tzinfo=utc)
        assert dates[6] == datetime(year=2013, month=8, day=1, tzinfo=utc)
        assert dates[7] == datetime(year=2013, month=9, day=1, tzinfo=utc)
        assert dates[8] == datetime(year=2013, month=10, day=1, tzinfo=utc)
        assert dates[9] == datetime(year=2013, month=11, day=1, tzinfo=utc)
        assert dates[10] == datetime(year=2013, month=12, day=1, tzinfo=utc)
        assert dates[11] == datetime(year=2014, month=1, day=1, tzinfo=utc)
        assert dates[12] == datetime(year=2014, month=1, day=9, tzinfo=utc)


    def test_organization_monthly_income(self):
        """Jan 2012: ABC has 2 customers,
        Feb 2012: ABC lost 1 customer,
        Mar 2012: ABC gains 1 customer,
        Apr 2012: ABC lost 1 customer and gains 1 customer,
        May 2012: No change."""
        table = organization_monthly_revenue_customers(
            Organization.objects.get(pk=2),
            from_date=date(year=2014, month=1, day=1))
        for entry in table:
            values = entry["values"]
            if entry["key"] == "Total # of Customers":
                assert values[0][1] == 2
                assert values[1][1] == 1
                assert values[2][1] == 2
                assert values[3][1] == 2
                assert values[4][1] == 2
                assert values[4][1] == 2
            elif entry["key"] == "# of new Customers":
                assert values[0][1] == 2  # We have no records before
                assert values[1][1] == 0
                assert values[2][1] == 1
                assert values[3][1] == 1
                assert values[4][1] == 0
                assert values[4][1] == 0
            elif entry["key"] == "# of churned Customers":
                assert values[0][1] == 0
                assert values[1][1] == 1
                assert values[2][1] == 0
                assert values[3][1] == 1
                assert values[4][1] == 0
                assert values[4][1] == 0




