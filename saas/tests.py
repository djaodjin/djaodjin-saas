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

from datetime import date, datetime
from unittest import skip

from django.test import TestCase
from django.utils.timezone import utc
from django.core.management import call_command
from django.db import transaction

from saas.managers.metrics import aggregate_monthly_transactions, month_periods
from saas.models import Organization, Transaction, Charge
from saas.charge import create_charges_for_balance


@skip("still pb committing the associated processor_id before the tests start")
class LedgerTests(TestCase):
    #pylint: disable=no-self-use
    """
    Tests ledger functionality.
    """
    fixtures = ['test_data']

    @classmethod
    def setUpClass(cls):
        # Transactions are discarded and fixtures reloaded after
        # each test case so we have to insure all organizations
        # have a valid procesor_id and associated credit card.

        # We have to use this slightly awkward syntax due to the fact
        # that we're using *args and **kwargs together.
        #pylint: disable=star-args
        call_command('loaddata', *['test_organization'],
                     **{'verbosity': 0, 'database': 'default',
                        'skip_validation': True})

        transaction.commit_unless_managed(using='default')
        transaction.enter_transaction_management(using='default')
        transaction.managed(True, using='default')
        for customer in Organization.objects.all():
            customer.update_card(
                card={'number': '4242424242424242',
                      'exp_month': '12',
                      'exp_year': '2014'})
        transaction.commit(using='default')
        transaction.leave_transaction_management(using='default')

    @staticmethod
    def _create_charge(customer_name, amount):
        customer = Organization.objects.get(slug=customer_name)
        invoiced_items = [Transaction.objects.create(
            created_at=datetime.utcnow().replace(tzinfo=utc),
            descr='reason for charge',
            orig_amount=amount,
            orig_account=Transaction.PAYABLE,
            orig_organization=customer,
            dest_amount=amount,
            dest_account=Transaction.FUNDS,
            dest_organization=customer)]
        charge = Charge.objects.charge_card(
            customer, invoiced_items)
        return customer, charge


    def _create_charge_for_balance(self, customer_name):
        customer = Organization.objects.get(slug=customer_name)
        prev_balance = Transaction.objects.get_organization_balance(customer)
        return self._create_charge(customer_name, prev_balance)

    def test_create_usage(self):
        _, processor_id = self._create_charge('abc', 1000)
        self.assertTrue(len(processor_id) > 0)

    def test_pay_now(self):
        """Pay the balance of account.
        No Issue."""
        customer, charge = self._create_charge_for_balance('abc')
        charge.payment_sucessful()
        next_balance = Transaction.objects.get_organization_balance(customer)
        self.assertTrue(next_balance == 0)

    def test_pay_now_two_success(self):
        """Pay the balance of account.
        Receive two 'charge.succeeded' events."""
        customer, charge = self._create_charge_for_balance('abc')
        charge.payment_sucessful()
        charge.payment_sucessful()
        next_balance = Transaction.objects.get_organization_balance(customer)
        self.assertTrue(next_balance == 0)

    def test_charge_cards(self):
        """Charge all customers credit cards for fees due
        since the last time the card was charged."""
        create_charges_for_balance(until=datetime(2013, 04, 21))
        assert True


#@skip("debugging")
class MetricsTests(TestCase):
    """
    Tests metrics functionality.
    """
    fixtures = ['test_organization', 'test_metrics']

    def test_month_periods_full_year(self):
        dates = month_periods(
            from_date=date(year=2014, month=1, day=1))
        self.assertTrue(len(dates) == 13)
        self.assertTrue(
            dates[0] == datetime(year=2013, month=1, day=1, tzinfo=utc))
        self.assertTrue(
            dates[1] == datetime(year=2013, month=2, day=1, tzinfo=utc))
        self.assertTrue(
            dates[2] == datetime(year=2013, month=3, day=1, tzinfo=utc))
        self.assertTrue(
            dates[3] == datetime(year=2013, month=4, day=1, tzinfo=utc))
        self.assertTrue(
            dates[4] == datetime(year=2013, month=5, day=1, tzinfo=utc))
        self.assertTrue(
            dates[5] == datetime(year=2013, month=6, day=1, tzinfo=utc))
        self.assertTrue(
            dates[6] == datetime(year=2013, month=7, day=1, tzinfo=utc))
        self.assertTrue(
            dates[7] == datetime(year=2013, month=8, day=1, tzinfo=utc))
        self.assertTrue(
            dates[8] == datetime(year=2013, month=9, day=1, tzinfo=utc))
        self.assertTrue(
            dates[9] == datetime(year=2013, month=10, day=1, tzinfo=utc))
        self.assertTrue(
            dates[10] == datetime(year=2013, month=11, day=1, tzinfo=utc))
        self.assertTrue(
            dates[11] == datetime(year=2013, month=12, day=1, tzinfo=utc))
        self.assertTrue(
            dates[12] == datetime(year=2014, month=1, day=1, tzinfo=utc))

    def test_incomplete_last_month(self):
        dates = month_periods(
            from_date=date(year=2014, month=1, day=9))
        self.assertTrue(len(dates) == 13)
        self.assertTrue(
            dates[0] == datetime(year=2013, month=2, day=1, tzinfo=utc))
        self.assertTrue(
            dates[1] == datetime(year=2013, month=3, day=1, tzinfo=utc))
        self.assertTrue(
            dates[2] == datetime(year=2013, month=4, day=1, tzinfo=utc))
        self.assertTrue(
            dates[3] == datetime(year=2013, month=5, day=1, tzinfo=utc))
        self.assertTrue(
            dates[4] == datetime(year=2013, month=6, day=1, tzinfo=utc))
        self.assertTrue(
            dates[5] == datetime(year=2013, month=7, day=1, tzinfo=utc))
        self.assertTrue(
            dates[6] == datetime(year=2013, month=8, day=1, tzinfo=utc))
        self.assertTrue(
            dates[7] == datetime(year=2013, month=9, day=1, tzinfo=utc))
        self.assertTrue(
            dates[8] == datetime(year=2013, month=10, day=1, tzinfo=utc))
        self.assertTrue(
            dates[9] == datetime(year=2013, month=11, day=1, tzinfo=utc))
        self.assertTrue(
            dates[10] == datetime(year=2013, month=12, day=1, tzinfo=utc))
        self.assertTrue(
            dates[11] == datetime(year=2014, month=1, day=1, tzinfo=utc))
        self.assertTrue(
            dates[12] == datetime(year=2014, month=1, day=9, tzinfo=utc))

    def test_monthly_income(self):
        """Jan 2012: ABC has 2 customers,
        Feb 2012: ABC lost 1 customer,
        Mar 2012: ABC gains 1 customer,
        Apr 2012: ABC lost 1 customer and gains 1 customer,
        May 2012: No change."""
        table, _, _ = aggregate_monthly_transactions(
            Organization.objects.get(pk=2),
            from_date=date(year=2014, month=1, day=1))
        for entry in table:
            values = entry["values"]
            if entry["key"] == "Total # of Customers":
                self.assertTrue(values[0][1] == 2)
                self.assertTrue(values[1][1] == 1)
                self.assertTrue(values[2][1] == 2)
                self.assertTrue(values[3][1] == 2)
                self.assertTrue(values[4][1] == 2)
                self.assertTrue(values[4][1] == 2)
            elif entry["key"] == "# of new Customers":
                self.assertTrue(values[0][1] == 2)  # We have no records before
                self.assertTrue(values[1][1] == 0)
                self.assertTrue(values[2][1] == 1)
                self.assertTrue(values[3][1] == 1)
                self.assertTrue(values[4][1] == 0)
                self.assertTrue(values[4][1] == 0)
            elif entry["key"] == "# of churned Customers":
                self.assertTrue(values[0][1] == 0)
                self.assertTrue(values[1][1] == 1)
                self.assertTrue(values[2][1] == 0)
                self.assertTrue(values[3][1] == 1)
                self.assertTrue(values[4][1] == 0)
                self.assertTrue(values[4][1] == 0)




