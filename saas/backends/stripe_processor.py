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
The Stripe backend works in 3 different modes:

  - ``LOCAL``
  - ``FORMWARD``
  - ``REMOTE``

In LOCAL mode, Stripe Customer and Charge objects are created on the Stripe
Account identified by settings.STRIPE_PRIV_KEY. All transfers are made to
the bank account associated to that account.

In FORWARD mode, Stripe Customer and Charge objects are also created on
the Stripe Account identified by settings.STRIPE_PRIV_KEY but each
Charge is tied automatically to a Stripe Transfer to a Stripe Connect Account.

In REMOTE mode, Stripe Customer and Charge objects are created on
the Stripe Connect Account.

To configure Stripe Connect, follow the instructions
at https://stripe.com/docs/connect,

Go to "Account Settings" > "Connect"

Edit the redirect_url and copy/paste the keys into your project settings.py:

    SAAS = {
        'STRIPE_CLIENT_ID': "...",
        'STRIPE_PRIV_KEY': "...",
        'STRIPE_PUB_KEY': "..."
    }
"""

import datetime, logging, re

from django.db import transaction
import requests, stripe

from saas import settings, signals
from saas.utils import datetime_or_now, datetime_to_timestamp

LOGGER = logging.getLogger(__name__)


class StripeBackend(object):

    LOCAL = 0
    FORWARD = 1
    REMOTE = 2

    def __init__(self):
        self.mode = self.LOCAL
        self.pub_key = settings.STRIPE_PUB_KEY
        self.priv_key = settings.STRIPE_PRIV_KEY
        self.client_id = settings.STRIPE_CLIENT_ID

    def _prepare_request(self, broker):
        stripe.api_key = self.priv_key
        if self.mode == self.REMOTE:
            # We have a Standalone account.
            kwargs = {'stripe_account': broker.processor_deposit_key}
        else:
            kwargs = {}
        return kwargs

    def list_customers(self, org_pat=r'.*', broker=None):
        """
        Returns a list of Stripe.Customer objects whose description field
        matches *org_pat*.
        """
        kwargs = self._prepare_request(broker)
        # customers are stored on the platform itself.
        customers = []
        nb_customers_listed = 0
        response = stripe.Customer.all(**kwargs)
        all_custs = response['data']
        while len(all_custs) > 0:
            for cust in all_custs:
                # We use the description field to store extra information
                # that connects the Stripe customer back to our database.
                if re.match(org_pat, cust.description):
                    customers.append(cust)
            nb_customers_listed = nb_customers_listed + len(all_custs)
            response = stripe.Customer.all(offset=nb_customers_listed, **kwargs)
            all_custs = response['data']
        return customers

    def charge_distribution(self, charge, refunded=0, unit='usd'):
        if charge.unit != unit:
            # Avoids an HTTP request to Stripe API when we can compute it.
            kwargs = self._prepare_request(charge.broker)
            balance_transactions = stripe.BalanceTransaction.all(
                source=charge.processor_key, **kwargs)
            # You would think to get all BalanceTransaction related to
            # the charge here but it is incorrect. You only get
            # the BalanceTransaction related to the original Charge.
            assert len(balance_transactions.data) == 1
            fee_unit = balance_transactions.data[0].currency
            fee_amount = balance_transactions.data[0].fee
            distribute_unit = balance_transactions.data[0].currency
            distribute_amount = balance_transactions.data[0].amount
            for refunds in stripe.Charge.retrieve(
                    charge.processor_key, **kwargs).refunds:
                balance_transaction = stripe.BalanceTransaction.retrieve(
                    refunds.balance_transaction, **kwargs)
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

    def connect_auth(self, organization, code):
        data = {'grant_type': 'authorization_code',
                'client_id': self.client_id,
                'client_secret': self.priv_key,
                'code': code}
        # Make /oauth/token endpoint POST request (XXX not available in stripe
        # library code?)
        resp = requests.post('https://connect.stripe.com/oauth/token',
            params=data)
        # Grab access_token (use this as your user's API key)
        data = resp.json()
        if resp.status_code != 200:
            LOGGER.info("[connect_auth] error headers: %s", resp.headers)
            raise stripe.error.AuthenticationError(
                message="%s: %s" % (data['error'], data['error_description']),
                http_body=resp.content, http_status=resp.status_code,
                json_body=data)
        LOGGER.info("%s authorized. %s", organization, data)
        organization.processor_pub_key = data.get('stripe_publishable_key')
        organization.processor_priv_key = data.get('access_token')
        organization.processor_deposit_key = data.get('stripe_user_id')
        organization.processor_refresh_token = data.get('refresh_token')

    def _create_charge(self, amount, unit,
            broker=None, descr=None, stmt_descr=None,
            customer=None, card=None):
        #pylint: disable=too-many-arguments
        assert customer is not None or card is not None
        kwargs = self._prepare_request(broker)
        if self.mode == self.FORWARD:
            kwargs.update({'destination': broker.processor_deposit_key})
        if customer is not None:
            kwargs.update({'customer': customer})
        elif card is not None:
            kwargs.update({'card': card})
        if stmt_descr is None and broker is not None:
            stmt_descr = broker.printable_name
        processor_charge = stripe.Charge.create(amount=amount, currency=unit,
            description=descr, statement_description=stmt_descr[:15], **kwargs)
        created_at = datetime.datetime.fromtimestamp(processor_charge.created)
        last4 = processor_charge.source.last4
        exp_year = processor_charge.source.exp_year
        exp_month = processor_charge.source.exp_month
        return (processor_charge.id, created_at, last4,
                datetime.date(exp_year, exp_month, 1))

    def create_charge(self, customer, amount, unit,
                    broker=None, descr=None, stmt_descr=None):
        #pylint: disable=too-many-arguments
        """
        Create a charge on the default card associated to the customer.

        *stmt_descr* can only be 15 characters maximum.
        """
        return self._create_charge(amount, unit,
            broker=broker, descr=descr, stmt_descr=stmt_descr,
            customer=customer.processor_card_key)

    def create_charge_on_card(self, card, amount, unit,
                    broker=None, descr=None, stmt_descr=None):
        #pylint: disable=too-many-arguments
        """
        Create a charge on a specified card.

        *stmt_descr* can only be 15 characters maximum.
        """
        return self._create_charge(amount, unit,
            broker=broker, descr=descr, stmt_descr=stmt_descr,
            card=card)

    def create_transfer(self, provider, amount, unit, descr=None):
        """
        Transfer *amount* from the platform into a provider bank account.
        """
        kwargs = self._prepare_request(None) # ``None`` because we can only
                              # transfer from the platform to the provider.
        if not provider.processor_priv_key:
            # We have a deprecated recipient key.
            kwargs.update({'recipient': provider.processor_deposit_key})
        transfer = stripe.Transfer.create(
            amount=amount,
            currency=unit, # XXX should be derived from organization bank
            description=descr,
            statement_description=provider.printable_name,
            **kwargs)
        created_at = datetime.datetime.fromtimestamp(transfer.created)
        return (transfer.id, created_at)

    def update_bank(self, provider, bank_token):
        """
        Create or update a bank account associated to a provider on Stripe.
        """
        kwargs = self._prepare_request(None) # ``None`` because we can only
                                  # edit bank details on a managed account.
        if not provider.processor_deposit_key:
            raise ValueError(
                "%s is not connected to a Stripe Account." % provider)
        try:
            if provider.processor_priv_key:
                # We have a Standalone account.
                rcp = stripe.Account.retrieve(**kwargs)
                rcp.bank_account = bank_token
                rcp.save()
            else:
                # We have a deprecated recipient key.
                rcp = stripe.Recipient.retrieve(
                    provider.processor_deposit_key, **kwargs)
                rcp.bank_account = bank_token
                rcp.save()
        except stripe.error.InvalidRequestError:
            LOGGER.error("update_bank(%s, %s)", provider, bank_token)

    def create_or_update_card(self, subscriber, card_token,
                              user=None, broker=None):
        """
        Create or update a card associated to an subscriber on Stripe.
        """
        kwargs = self._prepare_request(broker)
        # Save customer on the platform
        p_customer = None
        if subscriber.processor_card_key:
            try:
                p_customer = stripe.Customer.retrieve(
                    subscriber.processor_card_key, **kwargs)
                old_card = {'last4':p_customer.cards.data[0].last4,
                    'exp':"%d/%d" % (
                        p_customer.cards.data[0].exp_month,
                        p_customer.cards.data[0].exp_year)
                }
                p_customer.source = card_token
                p_customer.save()
                new_card = {'last4':p_customer.cards.data[0].last4,
                    'exp':"%d/%d" % (
                        p_customer.cards.data[0].exp_month,
                        p_customer.cards.data[0].exp_year)
                }
                signals.card_updated.send(
                    sender=__name__, organization=subscriber,
                    user=user, old_card=old_card, new_card=new_card)
            except stripe.error.InvalidRequestError:
                # Can't find the customer on Stripe. This can be related to
                # a switch from using devel to production keys.
                # We will seamlessly create a new customer on Stripe.
                LOGGER.warning("Retrieve customer %s on Stripe for %s",
                    subscriber.processor_card_key, subscriber)
        if not p_customer:
            p_customer = stripe.Customer.create(
                email=subscriber.email,
                description=subscriber.slug,
                card=card_token,
                **kwargs)
            subscriber.processor_card_key = p_customer.id
            subscriber.save()

    def refund_charge(self, charge, amount):
        """
        Refund a charge on the associated card.
        """
        kwargs = self._prepare_request(charge.broker)
        processor_charge = stripe.Charge.retrieve(
            charge.processor_key, **kwargs)
        processor_charge.refund(amount=amount)

    def retrieve_bank(self, provider):
        kwargs = self._prepare_request(None) # ``None`` because we can only
                              # retrieve bank details on a managed account.
        context = {'STRIPE_PUB_KEY': self.pub_key}
        try:
            if provider.processor_deposit_key:
                if provider.processor_priv_key:
                    # We have a Standalone account.
                    # XXX Apparently it is impossible to get the bank name
                    # nor the last4 of the bank account with this new feature.
                    rcp = stripe.Account.retrieve(**kwargs)
                    context.update({
                            'bank_name': 'See Stripe',
                            'last4': 'See Stripe',
                            'balance_unit': rcp.default_currency})
                else:
                    # We have a deprecated recipient key.
                    rcp = stripe.Recipient.retrieve(
                        provider.processor_deposit_key, **kwargs)
                    if rcp and rcp.active_account:
                        context.update({
                            'bank_name': rcp.active_account.bank_name,
                            'last4': '***-%s' % rcp.active_account.last4,
                            'balance_unit': rcp.active_account.currency})
        except stripe.error.InvalidRequestError:
            context.update({'bank_name': 'Unaccessible',
                'last4': 'Unaccessible', 'balance_unit': 'Unaccessible'})
        balance = stripe.Balance.retrieve(**kwargs)
        # XXX available is a list, ordered by currency?
        context.update({'balance_amount': balance.available[0].amount})
        return context

    def retrieve_card(self, subscriber, broker=None):
        kwargs = self._prepare_request(broker)
        # Customer is saved on the platform
        context = {'STRIPE_PUB_KEY': self.pub_key}
        if subscriber.processor_card_key:
            try:
                p_customer = stripe.Customer.retrieve(
                    subscriber.processor_card_key,
                    expand=['default_source'],
                    **kwargs)
            except stripe.error.StripeError as err:
                LOGGER.exception(err)
                raise
            if p_customer.default_source:
                last4 = '***-%s' % str(p_customer.default_source.last4)
                exp_date = "%02d/%04d" % (
                    p_customer.default_source.exp_month,
                    p_customer.default_source.exp_year)
                context.update({'last4': last4, 'exp_date': exp_date})
        return context

    def retrieve_charge(self, charge):
        # XXX make sure to avoid race condition.
        kwargs = self._prepare_request(charge.broker)
        if charge.is_progress:
            stripe_charge = stripe.Charge.retrieve(
                charge.processor_key, **kwargs)
            if stripe_charge.paid:
                charge.payment_successful()
        return charge

    def reconcile_transfers(self, provider):
        if provider.processor_deposit_key:
            balance = provider.withdraw_available()
            timestamp = datetime_to_timestamp(balance['created_at'])
            try:
                kwargs = self._prepare_request(provider)
                if not provider.processor_priv_key:
                    # We have a deprecated recipient key.
                    kwargs.update({'recipient': provider.processor_deposit_key})
                transfers = stripe.Transfer.all(
                    created={'gt': timestamp}, **kwargs)
                with transaction.atomic():
                    for transfer in transfers.data:
                        created_at = datetime_or_now(
                            datetime.datetime.fromtimestamp(transfer.created))
                        provider.create_withdraw_transactions(
                            transfer.id, transfer.amount, transfer.currency,
                            transfer.description, created_at=created_at)
            except stripe.error.InvalidRequestError as err:
                LOGGER.exception(err)

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
