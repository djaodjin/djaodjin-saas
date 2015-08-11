# Copyright (c) 2015, DjaoDjin inc.
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

import datetime, logging, re

import stripe

from saas import settings, signals

LOGGER = logging.getLogger('django.request') # We want ADMINS to about this.


class StripeBackend(object):

    def __init__(self):
        self.pub_key = settings.STRIPE_PUB_KEY
        self.priv_key = settings.STRIPE_PRIV_KEY

    def list_customers(self, org_pat=r'.*'):
        """
        Returns a list of Stripe.Customer objects whose description field
        matches *org_pat*.
        """
        stripe.api_key = self.priv_key
        customers = []
        nb_customers_listed = 0
        response = stripe.Customer.all()
        all_custs = response['data']
        while len(all_custs) > 0:
            for cust in all_custs:
                # We use the description field to store extra information
                # that connects the Stripe customer back to our database.
                if re.match(org_pat, cust.description):
                    customers.append(cust)
            nb_customers_listed = nb_customers_listed + len(all_custs)
            response = stripe.Customer.all(offset=nb_customers_listed)
            all_custs = response['data']
        return customers

    def charge_distribution(self, charge, refunded=0, unit='usd'):
        if charge.unit != unit:
            # Avoids an HTTP request to Stripe API when we can compute it.
            stripe.api_key = self.priv_key
            balance_transactions = stripe.BalanceTransaction.all(
                source=charge.processor_key)
            # You would think to get all BalanceTransaction related to
            # the charge here but it is incorrect. You only get
            # the BalanceTransaction related to the original Charge.
            assert len(balance_transactions.data) == 1
            fee_unit = balance_transactions.data[0].currency
            fee_amount = balance_transactions.data[0].fee
            distribute_unit = balance_transactions.data[0].currency
            distribute_amount = balance_transactions.data[0].amount
            for refunds in stripe.Charge.retrieve(charge.processor_key).refunds:
                balance_transaction = stripe.BalanceTransaction.retrieve(
                    refunds.balance_transaction)
                # fee and amount are negative
                fee_amount += balance_transaction.fee
                distribute_amount += balance_transaction.amount
        else:
            # Stripe processing fee associated to a transaction
            # is 2.9% + 30 cents.
            # Stripe rounds up so we do the same here. Be careful Python 3.x
            # semantics are broken and will return a float instead of a int.
            fee_unit = charge.unit
            available_amount = charge.amount - refunded
            if available_amount > 0:
                fee_amount = (available_amount * 290 + 5000) / 10000 + 30
            else:
                fee_amount = 0
            distribute_amount = available_amount - fee_amount
            distribute_unit = charge.unit
        return distribute_amount, distribute_unit, fee_amount, fee_unit

    def create_charge(self, organization, amount, unit,
        descr=None, stmt_descr=None):
        #pylint: disable=too-many-arguments
        """
        Create a charge on the default card associated to the organization.

        *stmt_descr* can only be 15 characters maximum.
        """
        stripe.api_key = self.priv_key
        processor_charge = stripe.Charge.create(
            amount=amount, currency=unit,
            customer=organization.processor_card_key,
            description=descr,
            statement_description=stmt_descr[:15])
        created_at = datetime.datetime.fromtimestamp(processor_charge.created)
        return (processor_charge.id, created_at,
                processor_charge.card.last4,
                datetime.date(processor_charge.card.exp_year,
                              processor_charge.card.exp_month, 1))

    def refund_charge(self, charge, amount):
        """
        Refund a charge on the associated card.
        """
        stripe.api_key = self.priv_key
        processor_charge = stripe.Charge.retrieve(charge.processor_key)
        processor_charge.refund(amount=amount)

    def create_charge_on_card(self, card, amount, unit,
        descr=None, stmt_descr=None):
        #pylint: disable=too-many-arguments
        """
        Create a charge on a specified card.

        *stmt_descr* can only be 15 characters maximum.
        """
        stripe.api_key = self.priv_key
        processor_charge = stripe.Charge.create(
            amount=amount, currency=unit,
            card=card, description=descr, statement_description=stmt_descr[:15])
        created_at = datetime.datetime.fromtimestamp(processor_charge.created)
        return (processor_charge.id, created_at,
                processor_charge.card.last4,
                datetime.date(processor_charge.card.exp_year,
                              processor_charge.card.exp_month, 1))

    def create_transfer(self, organization, amount, descr=None):
        """
        Transfer *amount* into the organization bank account.
        """
        stripe.api_key = self.priv_key
        transfer = stripe.Transfer.create(
            amount=amount,
            currency='usd', # XXX should be derived from organization bank
            recipient=organization.processor_recipient_id,
            description=descr,
            statement_description=organization.printable_name)
        created_at = datetime.datetime.fromtimestamp(transfer.created)
        return (transfer.id, created_at)

    def create_or_update_bank(self, organization, bank_token):
        """
        Create or update a bank account associated to an organization on Stripe.
        """
        stripe.api_key = self.priv_key
        rcp = None
        if organization.processor_recipient_id:
            try:
                rcp = stripe.Recipient.retrieve(
                    organization.processor_recipient_id)
                rcp.bank_account = bank_token
                rcp.save()
            except stripe.error.InvalidRequestError:
                LOGGER.error("Retrieve recipient %s",
                             organization.processor_recipient_id)
        if not rcp:
            rcp = stripe.Recipient.create(
                name=organization.printable_name,
                type="corporation",
                # XXX add tax id.
                email=organization.email,
                bank_account=bank_token)
            organization.processor_recipient_id = rcp.id
            organization.save()

    def create_or_update_card(self, organization, card_token, user=None):
        """
        Create or update a card associated to an organization on Stripe.
        """
        stripe.api_key = self.priv_key
        p_customer = None
        if organization.processor_card_key:
            try:
                p_customer = stripe.Customer.retrieve(
                    organization.processor_card_key)
                p_customer.card = card_token
                p_customer.save()
                signals.card_updated.send(
                    sender=__name__, organization=organization, user=user)
            except stripe.error.InvalidRequestError:
                # Can't find the customer on Stripe. This can be related to
                # a switch from using devel to production keys.
                # We will seamlessly create a new customer on Stripe.
                LOGGER.warning("Retrieve customer %s on Stripe for %s",
                    organization.processor_card_key, organization)
        if not p_customer:
            p_customer = stripe.Customer.create(
                email=organization.email,
                description=organization.slug,
                card=card_token)
            organization.processor_card_key = p_customer.id
            organization.save()

    def retrieve_bank(self, organization):
        stripe.api_key = self.priv_key
        context = {'STRIPE_PUB_KEY': self.pub_key}
        if organization.processor_recipient_id:
            try:
                rcp = stripe.Recipient.retrieve(
                    organization.processor_recipient_id)
                context.update({
                    'bank_name': rcp.active_account.bank_name,
                    'last4': '***-%s' % rcp.active_account.last4,
                    'currency': rcp.active_account.currency})
            except stripe.error.InvalidRequestError:
                context.update({'bank_name': 'Unaccessible',
                    'last4': 'Unaccessible', 'currency': 'Unaccessible'})
        return context

    def retrieve_card(self, organization):
        stripe.api_key = self.priv_key
        context = {'STRIPE_PUB_KEY': self.pub_key}
        if organization.processor_card_key:
            try:
                p_customer = stripe.Customer.retrieve(
                    organization.processor_card_key, expand=['default_card'])
            except stripe.error.StripeError as err:
                LOGGER.exception(err)
                raise
            if p_customer.default_card:
                last4 = '***-%s' % str(p_customer.default_card.last4)
                exp_date = "%02d/%04d" % (
                    p_customer.default_card.exp_month,
                    p_customer.default_card.exp_year)
                context.update({'last4': last4, 'exp_date': exp_date})
        return context

    def retrieve_charge(self, charge):
        # XXX make sure to avoid race condition.
        stripe.api_key = self.priv_key
        if charge.is_progress:
            stripe_charge = stripe.Charge.retrieve(charge.processor_key)
            if stripe_charge.paid:
                charge.payment_successful()
        return charge

    @staticmethod
    def dispute_fee(amount): #pylint: disable=unused-argument
        """
        Return Stripe processing fee associated to a chargeback (i.e. $15).
        """
        return 1500

    @staticmethod
    def prorate_transfer(amount): #pylint: disable=unused-argument
        """
        Return Stripe processing fee associated to a transfer (i.e. 25 cents).
        """
        return 25
