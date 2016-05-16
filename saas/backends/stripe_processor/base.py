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
Stripe configuration
--------------------

The `Stripe <https://stripe.com/>`_ backend works in 3 different modes:

  - ``LOCAL``
  - ``FORMWARD``
  - ``REMOTE``

In LOCAL mode, Stripe Customer and Charge objects are created on the Stripe
Account identified by settings.PROCESSOR['PRIV_KEY']. All transfers are made to
the bank account associated to that account.

In FORWARD mode, Stripe Customer and Charge objects are also created on
the Stripe Account identified by settings.PROCESSOR['PRIV_KEY'] but each
Charge is tied automatically to a Stripe Transfer to a Stripe Connect Account.

In REMOTE mode, Stripe Customer and Charge objects are created on
the Stripe Connect Account.

To configure Stripe Connect, follow the instructions
at https://stripe.com/docs/connect,

Go to "Account Settings" > "Connect"

Edit the redirect_url and copy/paste the keys into your project settings.py

.. code-block:: python

    SAAS = {
        'PROCESSOR': {
            'BACKEND': 'saas.backends.stripe_processor.StripeBackend',
            'PRIV_KEY': "...",
            'PUB_KEY': "...",
        # optional
            'CLIENT_ID': "...",
            'MODE': "...",
        }
    }
"""

import datetime, logging, re

from django.conf import settings as django_settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
import requests, stripe

from .. import CardError, ProcessorError
from ... import settings, signals
from ...utils import datetime_to_utctimestamp, utctimestamp_to_datetime

LOGGER = logging.getLogger(__name__)


class StripeBackend(object):

    LOCAL = 0
    FORWARD = 1
    REMOTE = 2

    token_id = 'stripeToken'

    def __init__(self):
        self.pub_key = settings.PROCESSOR['PUB_KEY']
        self.priv_key = settings.PROCESSOR['PRIV_KEY']
        self.client_id = settings.PROCESSOR.get('CLIENT_ID', None)
        self.mode = settings.PROCESSOR.get('MODE', 0)

    def _prepare_request(self):
        stripe.api_version = '2015-10-16'
        stripe.api_key = self.priv_key
        return {}

    def _prepare_charge_request(self, broker):
        kwargs = self._prepare_request()
        if self.mode == self.REMOTE and broker.slug != settings.PLATFORM:
            # We generate Stripe data into the StripeConnect account.
            if not broker.processor_deposit_key:
                raise ProcessorError(
                    "%s is not connected to a Stripe Account." % broker)
            kwargs.update({'stripe_account': broker.processor_deposit_key})
        return kwargs

    def _prepare_transfer_request(self, provider):
        kwargs = self._prepare_request()
        if (self.mode in (self.FORWARD, self.REMOTE)
            and provider.slug != settings.PLATFORM):
            # We generate Stripe data into the StripeConnect account.
            if not provider.processor_deposit_key:
                raise ProcessorError(
                    "%s is not connected to a Stripe Account." % provider)
            kwargs.update({'stripe_account': provider.processor_deposit_key})
        return kwargs


    def list_customers(self, org_pat=r'.*', broker=None):
        """
        Returns a list of Stripe.Customer objects whose description field
        matches *org_pat*.
        """
        kwargs = self._prepare_charge_request(broker)
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
            kwargs = self._prepare_charge_request(charge.broker)
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
        LOGGER.debug("charge_distribution(charge=%s, amount=%d %s)"\
            "distribute: %d %s, fee: %d %s",
            charge.processor_key, refunded, unit,
            distribute_amount, distribute_unit,
            fee_amount, fee_unit)
        return distribute_amount, distribute_unit, fee_amount, fee_unit

    def connect_auth(self, organization, code):
        data = {'grant_type': 'authorization_code',
                'client_id': self.client_id,
                'client_secret': self.priv_key,
                'code': code}
        if not settings.BYPASS_PROCESSOR_AUTH:
            # Make /oauth/token endpoint POST request
            # (XXX not available in stripe library code?)
            resp = requests.post('https://connect.stripe.com/oauth/token',
                params=data)
        else:
            # Use mockup bogus data
            resp = requests.Response()
            resp.status_code = 200
            #pylint:disable=protected-access
            resp._content = '{"stripe_publishable_key": "123456789",'\
                '"access_token": "123456789",'\
                '"stripe_user_id": "123456789",'\
                '"refresh_token": "123456789"}'
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
        kwargs = self._prepare_charge_request(broker)
        if self.mode == self.FORWARD and broker.slug != settings.PLATFORM:
            # We generate Stripe data into the StripeConnect account.
            if not broker.processor_deposit_key:
                raise ProcessorError(
                    "%s is not connected to a Stripe Account." % broker)
            kwargs.update({'destination': broker.processor_deposit_key})
        if customer is not None:
            kwargs.update({'customer': customer})
        elif card is not None:
            kwargs.update({'card': card})
        if stmt_descr is None and broker is not None:
            stmt_descr = broker.printable_name
        try:
            processor_charge = stripe.Charge.create(
                amount=amount, currency=unit,
                description=descr, statement_descriptor=stmt_descr[:15],
                **kwargs)
        except stripe.error.CardError, err:
            raise CardError(err.message, err.code, backend_except=err)
        created_at = utctimestamp_to_datetime(processor_charge.created)
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

    def create_transfer(self, provider, amount, currency, descr=None):
        """
        Manually transfer *amount* from the provider Stripe account
        into the provider bank account.
        """
        # XXX Stripe won't allow a Transfer to a Connect account.
        #     "Cannot create transfers with an OAuth key."
        kwargs = self._prepare_transfer_request(provider)
        transfer = stripe.Transfer.create(
            amount=amount,
            currency=currency, destination='default_for_currency',
            description=descr,
            statement_descriptor=provider.printable_name[:15],
            **kwargs)
        created_at = utctimestamp_to_datetime(transfer.created)
        return (transfer.id, created_at)

    def update_bank(self, provider, bank_token):
        """
        Create or update a bank account associated to a provider on Stripe.
        """
        kwargs = self._prepare_transfer_request(provider)
        try:
            rcp = stripe.Account.retrieve(**kwargs)
            # This will only work on "Managed" StripeConnect accounts.
            rcp.external_account = bank_token
            rcp.save()
        except stripe.error.InvalidRequestError:
            LOGGER.exception("update_bank(%s, %s)", provider, bank_token)
            raise

    def create_or_update_card(self, subscriber, card_token,
                              user=None, broker=None):
        """
        Create or update a card associated to an subscriber on Stripe.
        """
        kwargs = self._prepare_charge_request(broker)
        # Save customer on the platform
        p_customer = None
        if subscriber.processor_card_key:
            try:
                p_customer = stripe.Customer.retrieve(
                    subscriber.processor_card_key,
                    expand=['default_source'],
                    **kwargs)
                old_card = {'last4':p_customer.default_source.last4,
                    'exp':"%d/%d" % (
                        p_customer.default_source.exp_month,
                        p_customer.default_source.exp_year)
                }
                p_customer.source = card_token
                p_customer.save()
                p_customer = stripe.Customer.retrieve(
                    subscriber.processor_card_key,
                    expand=['default_source'],
                    **kwargs)
                new_card = {'last4':p_customer.default_source.last4,
                    'exp':"%d/%d" % (
                        p_customer.default_source.exp_month,
                        p_customer.default_source.exp_year)
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
        if p_customer is None:
            try:
                # XXX Seems either pylint or Stripe is wrong here...
                #pylint:disable=redefined-variable-type
                p_customer = stripe.Customer.create(
                    email=subscriber.email, description=subscriber.slug,
                    card=card_token, **kwargs)
            except stripe.error.CardError, err:
                raise CardError(err.message, err.code, backend_except=err)
            subscriber.processor_card_key = p_customer.id
            subscriber.save()

    def refund_charge(self, charge, amount):
        """
        Refund a charge on the associated card.
        """
        kwargs = self._prepare_charge_request(charge.broker)
        processor_charge = stripe.Charge.retrieve(
            charge.processor_key, **kwargs)
        processor_charge.refund(amount=amount)

    def get_deposit_context(self):
        # We insert the``STRIPE_CLIENT_ID`` here because we serve page
        # with a "Stripe Connect" button.
        context = {
            'STRIPE_PUB_KEY': self.pub_key,
            'STRIPE_CLIENT_ID': self.client_id
        }
        return context

    def retrieve_bank(self, provider):
        context = {}
        try:
            kwargs = self._prepare_transfer_request(provider)
            # The ``PLATFORM`` provider is always connected to a Stripe Account
            if (provider.processor_deposit_key
                or provider.slug == settings.PLATFORM):
                if provider.processor_deposit_key:
                    last4 = provider.processor_deposit_key[-4:]
                else:
                    last4 = self.pub_key[-4:]
                context.update({
                    'bank_name': 'Stripe', 'last4': '***-%s' % last4})
                try:
                    balance = stripe.Balance.retrieve(**kwargs)
                    # XXX available is a list, ordered by currency?
                    context.update({
                        'balance_amount': balance.available[0].amount,
                        'balance_unit': balance.available[0].currency})
                except stripe.error.InvalidRequestError:
                    context.update({'balance_unit': 'Unaccessible'})
        except ProcessorError:
            pass # OK here. We don't have a connected Stripe account.
        return context

    def retrieve_card(self, subscriber, broker=None):
        context = {'STRIPE_PUB_KEY': self.pub_key}
        try:
            kwargs = self._prepare_charge_request(broker)
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
        except ProcessorError:
            pass # OK here. We don't have a connected Stripe account.
        return context

    def retrieve_charge(self, charge):
        # XXX make sure to avoid race condition.
        kwargs = self._prepare_charge_request(charge.broker)
        if charge.is_progress:
            stripe_charge = stripe.Charge.retrieve(
                charge.processor_key, **kwargs)
            if stripe_charge.paid:
                charge.payment_successful()
        return charge

    def reconcile_transfers(self, provider, created_at):
        try:
            kwargs = self._prepare_transfer_request(provider)
            timestamp = datetime_to_utctimestamp(created_at)
            try:
                transfers = stripe.Transfer.all(
                    created={'gt': timestamp}, status='paid', **kwargs)
                for transfer in transfers.data:
                    created_at = utctimestamp_to_datetime(transfer.created)
                    provider.create_withdraw_transactions(
                        transfer.id, transfer.amount, transfer.currency,
                        transfer.description, created_at=created_at)
            except stripe.error.InvalidRequestError as err:
                LOGGER.exception(err)
        except ProcessorError:
            pass # OK here. We don't have a connected Stripe account.

    @staticmethod
    def dispute_fee(amount): #pylint: disable=unused-argument
        """
        Return Stripe processing fee associated to a chargeback (i.e. $15).
        """
        return 1500

    def prorate_transfer(self, amount, provider):
        #pylint: disable=unused-argument
        """
        Return Stripe processing fee associated to a transfer, i.e.
        0% for Stand-Alone Stripe accounts and 0.5% for managed accounts.
        """
        if False: #pylint:disable=using-constant-test
            # XXX Enable when using managed accounts.
            kwargs = self._prepare_transfer_request(provider)
            rcp = stripe.Account.retrieve(**kwargs)
            if rcp.managed:
                return (amount * 50 + 5000) / 10000
        return 0


@api_view(['POST'])
def processor_hook(request):
    from saas.models import Charge
    stripe.api_key = StripeBackend().priv_key
    # Attempt to validate the event by posting it back to Stripe.
    if django_settings.DEBUG:
        event = stripe.Event.construct_from(request.DATA, stripe.api_key)
    else:
        event = stripe.Event.retrieve(request.DATA['id'])
    if not event:
        LOGGER.error("Posted stripe '%s' event %s FAIL",
            event.type, request.DATA['id'])
        raise Http404
    LOGGER.info("Posted stripe '%s' event %s PASS", event.type, event.id)
    charge = get_object_or_404(Charge, processor_key=event.data.object.id)
    if event.type == 'charge.succeeded':
        if charge.state != charge.DONE:
            charge.payment_successful()
        else:
            LOGGER.warning(
                "Already received a charge.succeeded event for %s", charge)
    elif event.type == 'charge.failed':
        charge.failed()
    elif event.type == 'charge.refunded':
        charge.refund()
    elif event.type == 'charge.captured':
        charge.capture()
    elif event.type == 'charge.dispute.created':
        charge.dispute_created()
    elif event.type == 'charge.dispute.updated':
        charge.dispute_updated()
    elif event.type == 'charge.dispute.closed':
        if event.data.object.status == 'won':
            charge.dispute_won()
        elif event.data.object.status == 'lost':
            charge.dispute_lost()

    return Response("OK")
