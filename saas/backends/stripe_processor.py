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

from django.db import transaction
import requests, stripe

from saas import settings, signals
from saas.utils import datetime_or_now, datetime_to_timestamp

LOGGER = logging.getLogger(__name__)


class StripeBackend(object):

    def __init__(self):
        self.pub_key = settings.STRIPE_PUB_KEY
        self.priv_key = settings.STRIPE_PRIV_KEY
        self.client_id = settings.STRIPE_CLIENT_ID

    def _prepare_request(self, provider):
        stripe.api_key = self.priv_key
        if provider and provider.processor_pub_key:
            kwargs = {'stripe_account': provider.processor_deposit_key}
        else:
            kwargs = {}
        return kwargs

    @staticmethod
    def _charge_result(processor_charge):
        created_at = datetime.datetime.fromtimestamp(processor_charge.created)
        last4 = processor_charge.source.last4
        exp_year = processor_charge.source.exp_year
        exp_month = processor_charge.source.exp_month
        return (processor_charge.id, created_at, last4,
                datetime.date(exp_year, exp_month, 1))

    def list_customers(self, org_pat=r'.*'):
        """
        Returns a list of Stripe.Customer objects whose description field
        matches *org_pat*.
        """
        kwargs = self._prepare_request(provider=None)
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
            kwargs = self._prepare_request(charge.provider)
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
            raise stripe.error.AuthenticationError(
                message="%s: %s" % (data['error'], data['error_description']),
                http_body=resp.content, http_status=resp.status_code,
                json_body=data, headers=resp.headers)
        LOGGER.info("%s authorized. %s", organization, data)
        organization.processor_pub_key = data.get('stripe_publishable_key')
        organization.processor_priv_key = data.get('access_token')
        organization.processor_transfer_key = data.get('stripe_user_id')
        organization.processor_refresh_token = data.get('refresh_token')

    def create_charge(self, customer, amount, unit,
                      provider=None, descr=None, stmt_descr=None):
        #pylint: disable=too-many-arguments
        """
        Create a charge on the default card associated to the customer.

        *stmt_descr* can only be 15 characters maximum.
        """
        kwargs = self._prepare_request(provider)
        if stmt_descr is None and provider is not None:
            stmt_descr = provider.printable_name
        processor_charge = stripe.Charge.create(
            amount=amount, currency=unit, customer=customer.processor_card_key,
            description=descr, statement_description=stmt_descr[:15], **kwargs)
        return self._charge_result(processor_charge)

    def create_charge_on_card(self, card, amount, unit,
                              provider=None, descr=None, stmt_descr=None):
        #pylint: disable=too-many-arguments
        """
        Create a charge on a specified card.

        *stmt_descr* can only be 15 characters maximum.
        """
        kwargs = self._prepare_request(provider)
        if stmt_descr is None and provider is not None:
            stmt_descr = provider.printable_name
        processor_charge = stripe.Charge.create(
            amount=amount, currency=unit, card=card,
            description=descr, statement_description=stmt_descr[:15], **kwargs)
        return self._charge_result(processor_charge)

    def create_transfer(self, provider, amount, unit, descr=None):
        """
        Transfer *amount* into the organization bank account.
        """
        kwargs = self._prepare_request(provider)
        transfer = stripe.Transfer.create(
            amount=amount,
            currency=unit, # XXX should be derived from organization bank
            recipient=provider.processor_deposit_key,
            description=descr,
            statement_description=provider.printable_name,
            **kwargs)
        created_at = datetime.datetime.fromtimestamp(transfer.created)
        return (transfer.id, created_at)

    def create_or_update_bank(self, provider, bank_token):
        """
        Create or update a bank account associated to a provider on Stripe.
        """
        kwargs = self._prepare_request(provider)
        # XXX recipient on platform itself?
        rcp = None
        if provider.processor_deposit_key:
            try:
                rcp = stripe.Recipient.retrieve(
                    provider.processor_deposit_key, **kwargs)
                rcp.bank_account = bank_token
                rcp.save()
            except stripe.error.InvalidRequestError:
                LOGGER.error("Retrieve recipient %s",
                             provider.processor_deposit_key)
        if not rcp:
            rcp = stripe.Recipient.create(
                name=provider.printable_name,
                type="corporation",
                # XXX add tax id.
                email=provider.email,
                bank_account=bank_token,
                **kwargs)
            provider.processor_deposit_key = rcp.id
            provider.save()

    def create_or_update_card(self, organization, card_token, user=None):
        """
        Create or update a card associated to an organization on Stripe.
        """
        kwargs = self._prepare_request(provider=None)
        # Save customer on the platform
        p_customer = None
        if organization.processor_card_key:
            try:
                p_customer = stripe.Customer.retrieve(
                    organization.processor_card_key, **kwargs)
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
                    sender=__name__, organization=organization,
                    user=user, old_card=old_card, new_card=new_card)
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
                card=card_token,
                **kwargs)
            organization.processor_card_key = p_customer.id
            organization.save()

    def refund_charge(self, charge, amount):
        """
        Refund a charge on the associated card.
        """
        kwargs = self._prepare_request(charge.provider)
        processor_charge = stripe.Charge.retrieve(
            charge.processor_key, **kwargs)
        processor_charge.refund(amount=amount)

    def retrieve_bank(self, provider):
        kwargs = self._prepare_request(provider)
        context = {'STRIPE_PUB_KEY': self.pub_key}
        if provider.processor_deposit_key:
            try:
                rcp = stripe.Recipient.retrieve(
                    provider.processor_deposit_key, **kwargs)
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

    def retrieve_card(self, organization):
        kwargs = self._prepare_request(provider=None)
        # Customer is saved on the platform
        context = {'STRIPE_PUB_KEY': self.pub_key}
        if organization.processor_card_key:
            try:
                p_customer = stripe.Customer.retrieve(
                    organization.processor_card_key,
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
        kwargs = self._prepare_request(charge.provider)
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
                kwargs = self._prepare_request(provider=None)
                transfers = stripe.Transfer.all(created={'gt': timestamp},
                    recipient=provider.processor_deposit_key,
                    **kwargs)
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
