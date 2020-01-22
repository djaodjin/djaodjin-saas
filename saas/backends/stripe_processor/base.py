# Copyright (c) 2020, DjaoDjin inc.
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
The `Stripe <https://stripe.com/>`_ backend works in 3 different modes:

  - ``LOCAL``
  - ``FORMWARD``
  - ``REMOTE``

In LOCAL mode, Stripe Customer and Charge objects are created on the Stripe
Account identified by settings.PROCESSOR['PRIV_KEY']. All transfers are made to
the bank account associated to that account.

In FORWARD mode, Stripe Customer and Charge objects are also created on
the Stripe account identified by settings.PROCESSOR['PRIV_KEY'] but each
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
from __future__ import unicode_literals

import datetime, logging, re
from hashlib import sha512
from base64 import b64encode

from django.db import transaction
from django.utils import six
from django.utils.translation import ugettext_lazy as _
import requests, stripe

from .. import CardError, ProcessorError, ProcessorSetupError
from ... import settings, signals
from ...compat import reverse
from ...utils import (datetime_to_utctimestamp, utctimestamp_to_datetime,
    datetime_or_now, is_broker)


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
        self.mode = settings.PROCESSOR.get('MODE', self.LOCAL)

    def get_processor_charge(self, charge, includes_fee=False):
        stripe_charge = None
        headers = self._prepare_charge_request(charge.broker)
        kwargs = headers
        if includes_fee:
            kwargs = {}
            kwargs.update(headers)
            kwargs.update({'expand': ['application_fee',
                'balance_transaction', 'refunds.data.balance_transaction']})
        try:
            stripe_charge = stripe.Charge.retrieve(
                charge.processor_key, **kwargs)
        except stripe.error.InvalidRequestError:
            if (charge.processor_key in settings.PROCESSOR_FALLBACK and
                (self.mode == self.REMOTE and
                 not self._is_platform(charge.broker))):
                LOGGER.warning("Attempt fallback on charge %s.",
                    charge.processor_key)
                kwargs = self._prepare_request()
                stripe_charge = stripe.Charge.retrieve(
                    charge.processor_key, **kwargs)
        return stripe_charge, headers

    @staticmethod
    def _is_platform(provider):
        return provider._state.db == 'default' and is_broker(provider)

    def _prepare_request(self):
        stripe.api_version = '2019-08-14'
        stripe.api_key = self.priv_key
        return {}

    def _prepare_charge_request(self, broker):
        kwargs = self._prepare_request()
        if self.mode == self.REMOTE and not self._is_platform(broker):
            # We generate Stripe data into the StripeConnect account.
            if not broker.processor_deposit_key:
                raise ProcessorSetupError(
                    _("%(organization)s is not connected to a Stripe account."
                    ) % {'organization': broker}, broker)
            kwargs.update({'stripe_account': broker.processor_deposit_key})
        return kwargs

    def _prepare_transfer_request(self, provider):
        kwargs = self._prepare_request()
        if (self.mode in (self.FORWARD, self.REMOTE)
            and  not self._is_platform(provider)):
            # We generate Stripe data into the StripeConnect account.
            if not provider.processor_deposit_key:
                raise ProcessorSetupError(
                    _("%(organization)s is not connected to a Stripe account."
                    ) % {'organization': provider}, provider)
            kwargs.update({'stripe_account': provider.processor_deposit_key})
        return kwargs

    def is_configured(self):
        """
        Returns `True` if the configuration settings to connect with a Stripe
        account are present.
        """
        result = (self.pub_key and self.priv_key)
        if self.mode != self.LOCAL:
            result = (result and self.client_id)
        return result

    def list_customers(self, org_pat=r'.*', broker=None):
        """
        Returns a list of Stripe.Customer objects whose description field
        matches *org_pat*.
        """
        kwargs = self._prepare_charge_request(broker)
        customers = []
        nb_customers_listed = 0
        response = stripe.Customer.list(**kwargs)
        all_custs = response['data']
        while all_custs:
            for cust in all_custs:
                # We use the description field to store extra information
                # that connects the Stripe customer back to our database.
                if re.match(org_pat, cust.description):
                    customers.append(cust)
            nb_customers_listed = nb_customers_listed + len(all_custs)
            response = stripe.Customer.list(
                offset=nb_customers_listed, **kwargs)
            all_custs = response['data']
        return customers

    def charge_distribution(self, charge,
                            refunded=0, unit=settings.DEFAULT_UNIT):
        stripe_charge, kwargs = self.get_processor_charge(
            charge, includes_fee=True)
        LOGGER.debug("charge_distribution(charge=%s, refunded=%d, unit=%s)"\
            " => stripe_charge=\n%s", charge.processor_key, refunded, unit,
            stripe_charge)

        if not stripe_charge:
            return (charge.amount - refunded, unit,
                    0, unit,
                    0, unit)

        balance_transaction = stripe_charge.balance_transaction
        if isinstance(balance_transaction, six.string_types):
            balance_transaction = stripe.BalanceTransaction.retrieve(
                    stripe_charge.balance_transaction, **kwargs)
            LOGGER.debug(
                "charge_distribution(charge=%s, refunded=%d, unit=%s)"\
                " => balance_transaction=\n%s", charge.processor_key,
                refunded, unit, balance_transaction)

        distribute_amount = balance_transaction.net
        distribute_unit = balance_transaction.currency
        broker_fee_amount = 0
        broker_fee_unit = distribute_unit
        processor_fee_amount = 0
        processor_fee_unit = distribute_unit
        for stripe_fee in balance_transaction.fee_details:
            if stripe_fee.type == 'application_fee':
                broker_fee_amount = stripe_fee.amount
                broker_fee_unit = stripe_fee.currency
            elif stripe_fee.type == 'stripe_fee':
                processor_fee_amount = stripe_fee.amount
                processor_fee_unit = stripe_fee.currency

        for refund in stripe_charge.refunds:
            balance_transaction = refund.balance_transaction
            if isinstance(balance_transaction, six.string_types):
                balance_transaction = stripe.BalanceTransaction.retrieve(
                    balance_transaction, **kwargs)
                LOGGER.debug(
                    "charge_distribution(charge=%s, refunded=%d, unit=%s)"\
                    " => balance_transaction=\n%s", charge.processor_key,
                    refunded, unit, balance_transaction)
            # All amounts in refunds are negative
            distribute_amount += balance_transaction.net
            for stripe_fee in balance_transaction.fee_details:
                if stripe_fee.type == 'stripe_fee':
                    processor_fee_amount += stripe_fee.amount

        # Refunds of broker fee do not appear in refunds
        # but in application_fee.refunds instead.
        application_fee = stripe_charge.application_fee
        if application_fee:
            if isinstance(application_fee, six.string_types):
                application_fee = stripe.ApplicationFee.retrieve(
                    application_fee, **kwargs)
                LOGGER.debug(
                    "charge_distribution(charge=%s, refunded=%d, unit=%s)"\
                    " => application_fee=\n%s", charge.processor_key,
                    refunded, unit, application_fee)
            for stripe_fee in application_fee.refunds.data:
                if stripe_fee.object == 'fee_refund':
                    broker_fee_amount -= stripe_fee.amount
                    distribute_amount += stripe_fee.amount

        LOGGER.debug("charge_distribution(charge=%s, refunded=%d, unit=%s)"\
            " distribute: %d %s,"\
            " broker fee: %d %s,"\
            " processor fee: %d %s",
            charge.processor_key, refunded, unit,
            distribute_amount, distribute_unit,
            broker_fee_amount, broker_fee_unit,
            processor_fee_amount, processor_fee_unit)
        return (distribute_amount, distribute_unit,
                processor_fee_amount, processor_fee_unit,
                broker_fee_amount, broker_fee_unit)

    def connect_auth(self, organization, code):
        # setting those values to None in case the code has been used
        # before, which would result in an error and leave us with
        # invalid values
        organization.processor_pub_key = None
        organization.processor_priv_key = None
        organization.processor_deposit_key = None
        organization.processor_refresh_token = None

        data = {'grant_type': 'authorization_code',
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
                '"refresh_token": "123456789"}'.encode('utf-8')
        # Grab access_token (use this as your user's API key)
        data = resp.json()
        if resp.status_code != 200:
            LOGGER.debug("[connect_auth] error headers: %s", resp.headers)
            raise ProcessorError(
                message="%s: %s" % (data['error'], data['error_description']))
        LOGGER.debug("%s Stripe API returned: %s", organization, data)
        LOGGER.info("%s connect to Stripe authorized.", organization,
            extra={'event': 'connect-authorized', 'processor': 'stripe',
                'organization': organization.slug})
        organization.processor_pub_key = data.get('stripe_publishable_key')
        organization.processor_priv_key = data.get('access_token')
        organization.processor_deposit_key = data.get('stripe_user_id')
        organization.processor_refresh_token = data.get('refresh_token')

    def _create_charge(self, amount, unit, provider,
            descr=None, stmt_descr=None, created_at=None,
            broker_fee_amount=0, customer=None, card=None):
        #pylint: disable=too-many-arguments
        assert customer is not None or card is not None
        kwargs = self._prepare_charge_request(provider)
        if self.mode == self.FORWARD and not self._is_platform(provider):
            # We generate Stripe data into the StripeConnect account.
            if not provider.processor_deposit_key:
                raise ProcessorSetupError(
                    _("%(organization)s is not connected to a Stripe account."
                    ) % {'organization': provider}, provider)
            kwargs.update({'destination': provider.processor_deposit_key})
        if customer is not None:
            kwargs.update({'customer': customer})
        elif card is not None:
            kwargs.update({'card': card})
        if broker_fee_amount:
            kwargs.update({'application_fee_amount': broker_fee_amount})
        if stmt_descr is None and provider is not None:
            stmt_descr = provider.printable_name

        key = self.generate_idempotent_key(amount,
            unit, provider, descr, stmt_descr, created_at,
            customer, card)
        if key:
            kwargs.update({'idempotency_key': key})
        try:
            processor_charge = stripe.Charge.create(
                amount=amount, currency=unit,
                description=descr, statement_descriptor=stmt_descr[:15],
                **kwargs)
            processor_key = processor_charge.id
            LOGGER.debug("stripe.Charge.create(amount=%d, currency=%s,"\
                " description=%s, statement_descriptor=%s, kwargs=%s)"\
                " =>\n%s", amount, unit, descr, stmt_descr, kwargs,
                str(processor_charge))
            if created_at is None:
                # Implementation Note:
                #  We don't blindly use the `created` field from the Stripe
                #  Charge object because it seems to have dropped
                #  the microseconds accuracy recently. That's a problem
                #  whe `Transaction` are ordered and order->charge->receipt
                #  pipeline is script driven.
                created_at = utctimestamp_to_datetime(processor_charge.created)
            receipt_info = {
                'last4': processor_charge.source.last4,
                'exp_date': datetime.date(processor_charge.source.exp_year,
                    processor_charge.source.exp_month, 1),
                'card_name': processor_charge.source.name
            }
        except stripe.error.CardError as err:
            # If the card is declined, Stripe will record a failed ``Charge``
            # and raise an exception here. Unfortunately only the Charge id
            # is present in the CardError exception. So instead of generating
            # an HTTP retrieve and recording a failed charge in our database,
            # we raise and rollback.
            raise CardError(str(err), err.code,
                charge_processor_key=err.json_body['error']['charge'],
                backend_except=err)
        except stripe.error.PermissionError as err:
            # It is possible we no longer have access to the connected account.
            with transaction.atomic():
                # We want this update to be committed even if other transactions
                # are unwind on the exception.
                provider.processor_pub_key = None
                provider.processor_priv_key = None
                provider.processor_deposit_key = None
                provider.processor_refresh_token = None
                provider.save()
            raise ProcessorSetupError(
                    _("access to %(organization)s Stripe account was denied"\
                      " (access might have been revoked).") % {
                    'organization': provider}, provider, backend_except=err)
        except stripe.error.IdempotencyError as err:
            LOGGER.error(err)
        return (processor_key, created_at, receipt_info)

    def create_charge(self, customer, amount, unit, provider=None,
                      descr=None, stmt_descr=None, created_at=None,
                      broker_fee_amount=0):
        #pylint: disable=too-many-arguments
        """
        Create a charge on the default card associated to the customer.

        *stmt_descr* can only be 15 characters maximum.
        """
        return self._create_charge(amount, unit, provider,
            descr=descr, stmt_descr=stmt_descr, created_at=created_at,
            broker_fee_amount=broker_fee_amount,
            customer=customer.processor_card_key)

    def create_charge_on_card(self, card, amount, unit, provider,
                    descr=None, stmt_descr=None, created_at=None,
                    broker_fee_amount=0):
        #pylint: disable=too-many-arguments
        """
        Create a charge on a specified card.

        *stmt_descr* can only be 15 characters maximum.
        """
        return self._create_charge(amount, unit, provider,
            descr=descr, stmt_descr=stmt_descr, created_at=created_at,
            broker_fee_amount=broker_fee_amount,
            card=card)

    def create_transfer(self, provider, amount, currency, descr=None):
        """
        Manually transfer *amount* from the provider Stripe account
        into the provider bank account.
        """
        # XXX Stripe won't allow a Transfer to a Connect account.
        #     "Cannot create transfers with an OAuth key."
        # This needs to be revisited now because of Payouts API.
        kwargs = self._prepare_transfer_request(provider)
        key = self.generate_idempotent_key(provider, amount,
            currency, descr)
        if key:
            kwargs.update({'idempotency_key': key})
        try:
            transfer = stripe.Payout.create(
                amount=amount,
                currency=currency,
                description=descr,
                statement_descriptor=provider.printable_name[:15],
                **kwargs)
        except stripe.error.IdempotencyError as err:
            LOGGER.error(err)
        created_at = utctimestamp_to_datetime(transfer.created)
        return (transfer.id, created_at)

    def delete_card(self, subscriber, broker=None):
        """
        Removes a card associated to an subscriber.
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
                p_customer.default_source.delete()
            except stripe.error.CardError as err:
                raise CardError(str(err), err.code, backend_except=err)
            except stripe.error.InvalidRequestError:
                # Can't find the customer on Stripe. This can be related to
                # a switch from using devel to production keys.
                # We will seamlessly create a new customer on Stripe.
                LOGGER.warning("Retrieve customer %s on Stripe for %s",
                    subscriber.processor_card_key, subscriber)

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
        except stripe.error.InvalidRequestError as err:
            raise ProcessorError(str(err), backend_except=err)

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
                    'exp_date':"%d/%d" % (
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
                    'exp_date':"%d/%d" % (
                        p_customer.default_source.exp_month,
                        p_customer.default_source.exp_year)
                }
                signals.card_updated.send(
                    sender=__name__, organization=subscriber,
                    user=user, old_card=old_card, new_card=new_card)
            except stripe.error.CardError as err:
                raise CardError(str(err), err.code, backend_except=err)
            except stripe.error.InvalidRequestError:
                # Can't find the customer on Stripe. This can be related to
                # a switch from using devel to production keys.
                # We will seamlessly create a new customer on Stripe.
                LOGGER.warning("Retrieve customer %s on Stripe for %s",
                    subscriber.processor_card_key, subscriber)
        if p_customer is None:
            try:
                # XXX Seems either pylint or Stripe is wrong here...
                key = self.generate_idempotent_key(subscriber,
                    card_token, user, broker)
                if key:
                    kwargs.update({'idempotency_key': key})
                p_customer = stripe.Customer.create(
                    email=subscriber.email, description=subscriber.slug,
                    card=card_token, **kwargs)
            except stripe.error.CardError as err:
                raise CardError(str(err), err.code, backend_except=err)
            except stripe.error.IdempotencyError as err:
                LOGGER.error(err)
            subscriber.processor_card_key = p_customer.id
            # We rely on ``update_card`` to do the ``save``.

    def refund_charge(self, charge, amount, broker_amount):
        """
        Refund a charge on the associated card.
        """
        kwargs = self._prepare_charge_request(charge.broker)
        refund = stripe.Refund.create(
            charge=charge.processor_key,
            amount=amount,
            refund_application_fee=False,
            expand=['charge'],
            **kwargs)
        LOGGER.debug("refund_charge(charge=%s, amount=%d, broker_amount=%d)"\
            " => refund=\n%s", charge.processor_key, amount, broker_amount,
            refund)
        if broker_amount > 0:
            application_fee_refund = stripe.ApplicationFee.create_refund(
                refund.charge.application_fee, amount=broker_amount)
            LOGGER.debug(
                "refund_charge(charge=%s, amount=%d, broker_amount=%d)"\
                " => application_fee_refund=\n%s", charge.processor_key, amount,
                broker_amount, application_fee_refund)

    def get_authorize_url(self, provider, client_id=None, redirect_uri=None):
        if self._is_platform(provider):
            return None
        state = str(provider)
        connect_state_func = settings.PROCESSOR.get(
            'CONNECT_STATE_CALLABLE', None)
        if connect_state_func:
            from ...compat import import_string
            func = import_string(connect_state_func)
            state = func(self, provider)
        #pylint:disable=line-too-long
        data = {
            'client_id': client_id if client_id else self.client_id,
            'state': state
        }
        authorize_url = "https://connect.stripe.com/oauth/authorize?response_type=code&client_id=%(client_id)s&scope=read_write&state=%(state)s" % data
        if not redirect_uri:
            redirect_uri = settings.PROCESSOR_CONNECT_CALLBACK_URL
        if redirect_uri:
            authorize_url += "&redirect_uri=%s" % redirect_uri
        return authorize_url

    def get_deauthorize_url(self, provider):
        if self._is_platform(provider):
            return None
        return reverse('saas_deauthorize_processor', args=(provider,))

    def get_deposit_context(self):
        # We insert the``STRIPE_CLIENT_ID`` here because we serve page
        # with a "Stripe Connect" button.
        context = {
            'STRIPE_PUB_KEY': self.pub_key,
            'STRIPE_CLIENT_ID': self.client_id
        }
        return context

    def retrieve_bank(self, provider, includes_balance=True):
        context = {'bank_name': "N/A", 'last4': "N/A"}
        try:
            last4 = None
            if self._is_platform(provider):
                if self.priv_key:
                    last4 = self.priv_key[-min(len(self.priv_key), 4):]
            elif provider.processor_deposit_key:
                last4 = provider.processor_deposit_key[
                    -min(len(provider.processor_deposit_key), 4):]
            if last4:
                context.update({
                    'bank_name': 'Stripe', 'last4': '***-%s' % last4})

            if includes_balance:
                kwargs = self._prepare_transfer_request(provider)
                try:
                    balance = stripe.Balance.retrieve(**kwargs)
                    # XXX available is a list, ordered by currency?
                    context.update({
                        'balance_amount': balance.available[0].amount,
                        'balance_unit': balance.available[0].currency})
                except stripe.error.StripeError as err:
                    raise ProcessorError(str(err), backend_except=err)
        except ProcessorError:
            # OK here. We don't have a connected Stripe account.
            context.update({
                'balance_amount': "N/A",
                'balance_unit':  "N/A"})
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
                    LOGGER.exception("%s (mode=%s)", err,
                        "REMOTE" if kwargs else "LOCAL")
                    raise ProcessorError(str(err), backend_except=err)
                if p_customer.default_source:
                    last4 = '***-%s' % str(p_customer.default_source.last4)
                    exp_date = "%02d/%04d" % (
                        p_customer.default_source.exp_month,
                        p_customer.default_source.exp_year)
                    context.update({
                        'last4': last4, 'exp_date': exp_date,
                        'card_name': p_customer.default_source.name})
        except ProcessorError:
            pass # OK here. We don't have a connected Stripe account.
        return context

    def retrieve_charge(self, charge):
        return self._update_charge_state(charge)

    def _update_charge_state(self, charge, stripe_charge=None, event_type=None):
        if stripe_charge is None:
            stripe_charge, _ = self.get_processor_charge(charge)
        if event_type is None:
            if charge.is_progress:
                if stripe_charge.paid and stripe_charge.status == 'succeeded':
                    event_type = 'charge.succeeded'
                elif stripe_charge.status == 'failed':
                    event_type = 'charge.failed'
            if stripe_charge.dispute:
                event_type = 'charge.dispute.created'
        # Record state transition
        if event_type:
            if event_type == 'charge.succeeded':
                if charge.is_progress:
                    charge.payment_successful()
                else:
                    LOGGER.warning(
                        "Already received a state update event for %s", charge)
            elif event_type == 'charge.failed':
                charge.failed()
            elif event_type == 'charge.refunded':
                charge.refund()
            elif event_type == 'charge.captured':
                charge.capture()
            elif event_type == 'charge.dispute.created':
                if charge.is_disputed:
                    LOGGER.warning(
                        "Already received a state update event for %s", charge)
                else:
                    charge.dispute_created()
            elif event_type == 'charge.dispute.updated':
                charge.dispute_updated()
            elif event_type == 'charge.dispute.closed.won':
                charge.dispute_won()
            elif event_type == 'charge.dispute.closed.lost':
                charge.dispute_lost()

        return charge

    def reconcile_transfers(self, provider, created_at,
                            limit_to_one_request=False, dry_run=False):
        kwargs = self._prepare_transfer_request(provider)
        timestamp = datetime_to_utctimestamp(created_at)
        LOGGER.info("reconcile transfers from Stripe at %s", created_at)
        try:
            offset = 0
            transfers = stripe.Payout.list(
                created={'gt': timestamp}, status='paid',
                offset=offset, **kwargs)
            while transfers.data:
                for transfer in transfers.data:
                    created_at = utctimestamp_to_datetime(transfer.created)
                    descr = (transfer.description if transfer.description
                        else "STRIPE TRANSFER %s" % str(transfer.id))
                    provider.create_withdraw_transactions(
                        transfer.id, transfer.amount, transfer.currency,
                        descr, created_at=created_at, dry_run=dry_run)
                if limit_to_one_request:
                    break
                offset = offset + len(transfers.data)
                transfers = stripe.Payout.list(
                    created={'gt': timestamp}, status='paid',
                    offset=offset, **kwargs)
        except stripe.error.StripeError as err:
            raise ProcessorError(str(err), backend_except=err)

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
                # integer division
                return (amount * 50 + 5000) // 10000
        return 0

    @staticmethod
    def generate_idempotent_key(*data):
        key = ''
        if data:
            hsh = sha512()
            today = datetime_or_now()
            data = list(data)
            data.append(today)
            items = [str(value) for value in data if value is not None]
            hsh.update('|'.join(items).encode())
            key = b64encode(hsh.digest()).decode()
        return key
