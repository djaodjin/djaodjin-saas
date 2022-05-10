# Copyright (c) 2022, DjaoDjin inc.
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
  - ``FORWARD``
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
#pylint:disable=too-many-lines

from __future__ import unicode_literals

import datetime, logging, re
from hashlib import sha512
from base64 import b64encode

from django.db import transaction
import stripe

from .. import CardError, ProcessorError, ProcessorSetupError
from ... import settings, signals
from ...compat import (import_string, gettext_lazy as _, reverse, six)
from ...utils import (datetime_to_utctimestamp, utctimestamp_to_datetime,
    datetime_or_now)


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
        self.connect_callback_url = settings.PROCESSOR.get(
            'CONNECT_CALLBACK_URL', None)

    def _get_processor_charge(self, stripe_charge_key, broker,
                              includes_fee=False):
        stripe_charge = None
        headers = self._prepare_charge_request(broker)
        kwargs = headers
        if includes_fee:
            kwargs = {}
            kwargs.update(headers)
            kwargs.update({'expand': ['application_fee',
                'balance_transaction', 'refunds.data.balance_transaction']})
        if stripe_charge_key.startswith('ch_'):
            try:
                stripe_charge = stripe.Charge.retrieve(
                    stripe_charge_key, **kwargs)
            except stripe.error.InvalidRequestError:
                if (stripe_charge_key in settings.PROCESSOR_FALLBACK and
                    (self.mode == self.REMOTE and
                     not self._is_platform(broker))):
                    LOGGER.warning("Attempt fallback on charge %s.",
                        stripe_charge_key)
                    kwargs = self._prepare_request()
                    stripe_charge = stripe.Charge.retrieve(
                        stripe_charge_key, **kwargs)
        else:
            try:
                payment_intent = stripe.PaymentIntent.retrieve(
                    stripe_charge_key, **kwargs)
                if payment_intent.charges.data:
                    stripe_charge = payment_intent.charges.data[0]
            except stripe.error.StripeErrorWithParamCode as err:
                raise CardError(str(err), err.code, backend_except=err)
            except stripe.error.AuthenticationError as err:
                raise ProcessorSetupError(
                    _("Invalid request on processor for %(organization)s") % {
                    'organization': broker}, broker, backend_except=err)
            except stripe.error.StripeError as err:
                LOGGER.exception(err)
                raise ProcessorError(str(err), backend_except=err)

        return stripe_charge, headers

    @staticmethod
    def _is_platform(provider):
        #pylint:disable=protected-access
        return provider._state.db == 'default' and provider.is_broker

    def _prepare_request(self):
        stripe.api_version = '2020-08-27'
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
            # https://stripe.com/docs/connect/enable-payment-acceptance-guide?\
            #platform=web#create-a-payment-intent
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

    def requires_provider_keys(self):
        """
        Returns `True` if Stripe requires a provider key along
        with the StripeConnect keys.
        """
        return self.mode != self.LOCAL

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
        #pylint:disable=too-many-locals
        stripe_charge, kwargs = self._get_processor_charge(
            charge.processor_key, charge.broker, includes_fee=True)
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

        if not settings.BYPASS_PROCESSOR_AUTH:
            # Requires stripe version published after 2017
            try:
                self._prepare_request()
                data = stripe.OAuth.token(
                    grant_type='authorization_code',
                    code=code)
            except stripe.error.StripeError as err:
                LOGGER.exception(err)
                raise ProcessorError(str(err), backend_except=err)
        else:
            # Use mockup bogus data
            data = {
                "stripe_publishable_key": "123456789",
                "access_token": "123456789",
                "stripe_user_id": "123456789",
                "refresh_token": "123456789"
            }
        LOGGER.debug("%s Stripe API returned: %s", organization, data)
        LOGGER.info("%s connect to Stripe authorized.", organization,
            extra={'event': 'connect-authorized', 'processor': 'stripe',
                'organization': organization.slug})
        organization.processor_pub_key = data.get('stripe_publishable_key')
        organization.processor_priv_key = data.get('access_token')
        organization.processor_deposit_key = data.get('stripe_user_id')
        organization.processor_refresh_token = data.get('refresh_token')

    def create_payment(self, amount, unit, provider,
                       processor_card_key=None, token=None,
                       descr=None, stmt_descr=None, created_at=None,
                       broker_fee_amount=0):
        """
        Create either a Stripe ``Charge`` or ``PaymentIntent`` for an *amount*
        of *unit* (ex: $12) if *processor_card_key*/*token* is set or
        neither is set respectively.

        Create a charge on the default card associated to the customer
        if processor_card_key is set or on a specific card is token
        is set.

        *stmt_descr* can only be 15 characters maximum.
        """
        #pylint: disable=too-many-arguments,too-many-locals,too-many-statements
        assert processor_card_key is not None or token is not None
        kwargs = self._prepare_charge_request(provider)
        if self.mode == self.FORWARD and not self._is_platform(provider):
            # We generate Stripe data into the StripeConnect account.
            if not provider.processor_deposit_key:
                raise ProcessorSetupError(
                    _("%(organization)s is not connected to a Stripe account."
                    ) % {'organization': provider}, provider)
            kwargs.update({'destination': provider.processor_deposit_key})

        receipt_info = {}
        if token and token.startswith('pi_'):
            # We are dealing with a PaymentIntent. The Stripe Charge has
            # already been created.
            try:
                payment_intent = stripe.PaymentIntent.retrieve(id=token,
                    **kwargs)
                LOGGER.debug("stripe.PaymentIntent.retrieve("\
                    "id=%s, kwargs=%s) =>\n%s",
                    token, kwargs, str(payment_intent))
                if payment_intent.charges.data:
                    stripe_charge = payment_intent.charges.data[0]
            except stripe.error.StripeErrorWithParamCode as err:
                raise CardError(str(err), err.code, backend_except=err)
            except stripe.error.AuthenticationError as err:
                raise ProcessorSetupError(
                    _("Invalid request on processor for %(organization)s") % {
                    'organization': provider}, provider, backend_except=err)
            except stripe.error.StripeError as err:
                LOGGER.exception(err)
                raise ProcessorError(str(err), backend_except=err)
        else:
            try:
                if processor_card_key is not None:
                    stripe_customer = stripe.Customer.retrieve(
                        processor_card_key,
                        expand=['invoice_settings.default_payment_method'],
                        **kwargs)
                    kwargs.update({
                        'customer': processor_card_key,
                        'payment_method': stripe_customer.invoice_settings\
                            .default_payment_method,
                    })
                elif token is not None:
                    kwargs.update({'payment_method_data': {
                        'type': 'card', 'card': {'token': token}}
                    })
                if broker_fee_amount:
                    kwargs.update({'application_fee_amount': broker_fee_amount})
                if stmt_descr is None and provider is not None:
                    stmt_descr = provider.printable_name

                idempotency_key = self.generate_idempotent_key(amount,
                    unit, provider, descr, stmt_descr, created_at,
                    processor_card_key, token)
                payment_intent = stripe.PaymentIntent.create(
                    amount=amount, currency=unit,
                    description=descr, statement_descriptor=stmt_descr[:15],
                    off_session=True,
                    confirm=True,
                    idempotency_key=idempotency_key,
                    **kwargs)
                if payment_intent.charges.data:
                    stripe_charge = payment_intent.charges.data[0]
                LOGGER.debug("stripe.PaymentIntent.create("\
                    "amount=%d, currency=%s, description=%s, "\
                    "statement_descriptor=%s, kwargs=%s)"\
                    " =>\n%s\nstripe_charge=%s",
                    amount, unit, descr, stmt_descr, kwargs,
                    str(payment_intent), str(stripe_charge))
            except stripe.error.StripeErrorWithParamCode as err:
                # If the card is declined, Stripe will record a failed
                # ``Charge`` and raise an exception here. Unfortunately only
                # the Charge id is present in the CardError exception.
                # So instead of generating
                # an HTTP retrieve and recording a failed charge in our
                # database, we raise and rollback.
                raise CardError(str(err), err.code,
                    charge_processor_key=err.json_body['error']['charge'],
                    backend_except=err)
            except (stripe.error.AuthenticationError,
                    stripe.error.PermissionError) as err:
                # It is possible we no longer have access to the connected
                # account.
                with transaction.atomic():
                    # We want this update to be committed even if other
                    # transactions are unwind on the exception.
                    provider.processor_pub_key = None
                    provider.processor_priv_key = None
                    provider.processor_deposit_key = None
                    provider.processor_refresh_token = None
                    provider.save()
                raise ProcessorSetupError(
                    _("access to %(organization)s Stripe account was denied"\
                      " (access might have been revoked).") % {
                    'organization': provider}, provider, backend_except=err)
            except stripe.error.StripeError as err:
                LOGGER.exception(err)
                raise ProcessorError(str(err), backend_except=err)

        processor_key = stripe_charge.id
        if created_at is None:
            # Implementation Note:
            #  We don't blindly use the `created` field from the Stripe
            #  PaymentIntent object because it seems to have dropped
            #  the microseconds accuracy recently. That's a problem
            #  whe `Transaction` are ordered and order->charge->receipt
            #  pipeline is script driven.
            created_at = utctimestamp_to_datetime(stripe_charge.created)
        receipt_info.update({
            'last4': stripe_charge.payment_method_details.card.last4,
            'exp_date': datetime.date(
                stripe_charge.payment_method_details.card.exp_year,
                stripe_charge.payment_method_details.card.exp_month, 1),
            'card_name': stripe_charge.billing_details.name
        })

        return (processor_key, created_at, receipt_info)


    def create_transfer(self, provider, amount, currency, descr=None):
        """
        Manually transfer *amount* from the provider Stripe account
        into the provider bank account.
        """
        # XXX Stripe won't allow a Transfer to a Connect account.
        #     "Cannot create transfers with an OAuth key."
        # This needs to be revisited now because of Payouts API.
        kwargs = self._prepare_transfer_request(provider)
        try:
            transfer = stripe.Payout.create(
                amount=amount,
                currency=currency,
                description=descr,
                statement_descriptor=provider.printable_name[:15],
                idempotency_key=self.generate_idempotent_key(
                    provider, amount, currency, descr),
                **kwargs)
        except stripe.error.StripeErrorWithParamCode as err:
            raise CardError(str(err), err.code, backend_except=err)
        except stripe.error.AuthenticationError as err:
            raise ProcessorSetupError(
                _("Invalid request on processor for %(organization)s") % {
                'organization': provider}, provider, backend_except=err)
        except stripe.error.StripeError as err:
            LOGGER.exception(err)
            raise ProcessorError(str(err), backend_except=err)

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
                    expand=['invoice_settings.default_payment_method'],
                    **kwargs)
                stripe.PaymentMethod.detach(
                    p_customer.invoice_settings.default_payment_method)
            except stripe.error.CardError as err:
                raise CardError(str(err), err.code, backend_except=err)
            except stripe.error.InvalidRequestError:
                # Can't find the customer on Stripe. This can be related to
                # a switch from using devel to production keys.
                # We will seamlessly create a new customer on Stripe.
                LOGGER.warning("Retrieve customer %s on Stripe for %s",
                    subscriber.processor_card_key, subscriber)
            except stripe.error.StripeError as err:
                LOGGER.exception(err)
                raise ProcessorError(str(err), backend_except=err)

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
        except stripe.error.StripeErrorWithParamCode as err:
            raise CardError(str(err), err.code, backend_except=err)
        except stripe.error.AuthenticationError as err:
            raise ProcessorSetupError(
                _("Invalid request on processor for %(organization)s") % {
                'organization': provider}, provider, backend_except=err)
        except stripe.error.StripeError as err:
            LOGGER.exception(err)
            raise ProcessorError(str(err), backend_except=err)

    def create_or_update_card(self, subscriber, token,
                              user=None, broker=None):
        """
        Create or update a card associated to an subscriber on Stripe.
        """
        #pylint:disable=too-many-statements
        kwargs = self._prepare_charge_request(broker)

        old_card = {}
        p_customer = None
        if subscriber.processor_card_key:
            try:
                p_customer = stripe.Customer.retrieve(
                    subscriber.processor_card_key,
                    expand=['invoice_settings.default_payment_method',
                            'default_source'], **kwargs)
                old_card = self._retrieve_card(subscriber, broker=broker,
                    stripe_customer=p_customer)
            except stripe.error.CardError as err:
                raise CardError(str(err), err.code, backend_except=err)
            except stripe.error.InvalidRequestError as err:
                # Can't find the customer on Stripe. This can be related to
                # a switch from using devel to production keys.
                # We will seamlessly create a new customer on Stripe.
                LOGGER.warning("Retrieve customer %s on Stripe for %s: %s",
                    subscriber.processor_card_key, subscriber, err)
            except stripe.error.StripeError as err:
                LOGGER.exception(err)
                raise ProcessorError(str(err), backend_except=err)

        if token.startswith('pi_'):
            payment_intent = stripe.PaymentIntent.retrieve(id=token, **kwargs)
            card_token = payment_intent.payment_method
            if not subscriber.processor_card_key:
                subscriber.processor_card_key = payment_intent.customer
                # We rely on caller (``update_card``) to do the ``save``.
        elif token.startswith('seti_'):
            setup_intent = stripe.SetupIntent.retrieve(id=token, **kwargs)
            card_token = setup_intent.payment_method
            if not subscriber.processor_card_key:
                subscriber.processor_card_key = setup_intent.customer
                # We rely on caller (``update_card``) to do the ``save``.
        else:
            try:
                if p_customer is None:
                    p_customer = stripe.Customer.create(
                        email=subscriber.email, description=subscriber.slug,
                        idempotency_key=self.generate_idempotent_key(
                            subscriber, user, broker),
                        **kwargs)
                    subscriber.processor_card_key = p_customer.id
                    # We rely on caller (``update_card``) to do the ``save``.

                if self.mode == self.REMOTE:
                    # Implementation note: If we try to create a SetupIntent
                    # on a Connect account, Stripe complains that the card
                    # token is invalid. Stripe is though happy to use it
                    # as a customer source and convert that default source
                    # to a payment method afterwards.
                    p_customer.source = token
                    p_customer.save()
                    p_customer = stripe.Customer.retrieve(
                        subscriber.processor_card_key,
                        expand=['invoice_settings.default_payment_method',
                                'default_source'], **kwargs)
                    card_token = p_customer.default_source
                else:
                    # Implementation note: If we create a SetupIntent on
                    # the Stripe account itself, then we donot have issues
                    # with invalid tokens.
                    setup_intent = stripe.SetupIntent.create(
                        confirm=True,
                        usage='off_session',
                        customer=p_customer,
                        payment_method_data={
                            'type': 'card', 'card': {'token': token}},
                        **kwargs)
                    card_token = setup_intent.payment_method
            except stripe.error.StripeErrorWithParamCode as err:
                raise CardError(str(err), err.code, backend_except=err)
            except stripe.error.AuthenticationError as err:
                raise ProcessorSetupError(
                    _("Invalid request on processor for %(organization)s") % {
                    'organization': broker}, broker, backend_except=err)
            except stripe.error.StripeError as err:
                LOGGER.exception(err)
                raise ProcessorError(str(err), backend_except=err)

        try:
            stripe.Customer.modify(subscriber.processor_card_key,
                invoice_settings={'default_payment_method': card_token},
                **kwargs)
            new_card = self._retrieve_card(subscriber, broker=broker)
            if old_card:
                signals.card_updated.send(
                    sender=__name__, organization=subscriber,
                    user=user, old_card=old_card, new_card=new_card)
        except stripe.error.StripeErrorWithParamCode as err:
            raise CardError(str(err), err.code, backend_except=err)
        except stripe.error.AuthenticationError as err:
            raise ProcessorSetupError(
                _("Invalid request on processor for %(organization)s") % {
                'organization': broker}, broker, backend_except=err)
        except stripe.error.StripeError as err:
            LOGGER.exception(err)
            raise ProcessorError(str(err), backend_except=err)

        return new_card

    def refund_charge(self, charge, amount, broker_amount):
        """
        Refund a charge on the associated card.
        """
        kwargs = self._prepare_charge_request(charge.broker)
        try:
            refund = stripe.Refund.create(
                charge=charge.processor_key,
                amount=amount,
                refund_application_fee=False,
                expand=['charge'],
                **kwargs)
            LOGGER.debug(
                "refund_charge(charge=%s, amount=%d, broker_amount=%d)"\
                " => refund=\n%s", charge.processor_key, amount, broker_amount,
                refund)
            if broker_amount > 0:
                application_fee_refund = stripe.ApplicationFee.create_refund(
                    refund.charge.application_fee, amount=broker_amount)
                LOGGER.debug(
                    "refund_charge(charge=%s, amount=%d, broker_amount=%d)"\
                    " => application_fee_refund=\n%s", charge.processor_key,
                    amount, broker_amount, application_fee_refund)
        except stripe.error.StripeErrorWithParamCode as err:
            raise CardError(str(err), err.code, backend_except=err)
        except stripe.error.AuthenticationError as err:
            raise ProcessorSetupError(
                _("Invalid request on processor for %(organization)s") % {
                'organization': charge.broker}, charge.broker,
                backend_except=err)
        except stripe.error.StripeError as err:
            LOGGER.exception(err)
            raise ProcessorError(str(err), backend_except=err)

    def get_authorize_url(self, provider, client_id=None, redirect_uri=None):
        if self._is_platform(provider):
            return None
        state = str(provider)
        connect_state_func = settings.PROCESSOR.get(
            'CONNECT_STATE_CALLABLE', None)
        if connect_state_func:
            func = import_string(connect_state_func)
            state = func(self, provider)
        #pylint:disable=line-too-long
        data = {
            'client_id': client_id if client_id else self.client_id,
            'state': state
        }
        authorize_url = "https://connect.stripe.com/oauth/authorize?response_type=code&client_id=%(client_id)s&scope=read_write&state=%(state)s" % data
        if not redirect_uri:
            redirect_uri = self.connect_callback_url
        if redirect_uri:
            authorize_url += "&redirect_uri=%s" % redirect_uri
        return authorize_url

    def get_deauthorize_url(self, provider):
        if self._is_platform(provider):
            return None
        return reverse('saas_deauthorize_processor', args=(provider,))

    def get_payment_context(self, provider, processor_card_key,
                            amount=None, unit=None, broker_fee_amount=0,
                            subscriber_email=None, subscriber_slug=None):
        """
        Returns a dictionnary of values that needs to be passed to the browser
        client in order for the processor to create a payment.
        """
        #pylint:disable=too-many-arguments
        context = {
            'STRIPE_PUB_KEY': self.pub_key,
        }

        if not settings.PROCESSOR.get('USE_STRIPE_V3', False):
            return context

        if amount is not None and amount == 0:
            return context

        kwargs = self._prepare_charge_request(provider)
        if self.mode == self.FORWARD and not self._is_platform(provider):
            # We generate Stripe data into the StripeConnect account.
            if not provider.processor_deposit_key:
                raise ProcessorSetupError(
                    _("%(organization)s is not connected to a Stripe account."
                    ) % {'organization': provider}, provider)
            kwargs.update({'destination': provider.processor_deposit_key})

        try:
            if processor_card_key is None:
                p_customer = stripe.Customer.create(
                    email=subscriber_email, description=subscriber_slug,
                    idempotency_key=self.generate_idempotent_key(
                        subscriber_slug, provider),
                    **kwargs)
                processor_card_key = p_customer.id
            kwargs.update({'customer': processor_card_key})

            if amount is None:
                # We are updating a card for later payments.
                setup_intent = stripe.SetupIntent.create(**kwargs)
                LOGGER.debug("stripe.PaymentIntent.create("\
                    "amount=%d, currency=%s, kwargs=%s) =>\n%s",
                    amount, unit, kwargs, str(setup_intent))
                context.update({
                    'STRIPE_INTENT_SECRET': setup_intent.client_secret})
                if 'stripe_account' in kwargs:
                    context.update({
                        'STRIPE_ACCOUNT': kwargs.get('stripe_account')})

            elif amount > 0:
                if broker_fee_amount:
                    kwargs.update({'application_fee_amount': broker_fee_amount})
                try:
                    payment_intent = stripe.PaymentIntent.create(
                        amount=amount, currency=unit,
                        setup_future_usage='off_session',
                        **kwargs)
                    LOGGER.debug("stripe.PaymentIntent.create("\
                        "amount=%d, currency=%s, kwargs=%s) =>\n%s",
                        amount, unit, kwargs, str(payment_intent))
                    context.update({
                        'STRIPE_INTENT_SECRET': payment_intent.client_secret})
                    if 'stripe_account' in kwargs:
                        context.update({
                            'STRIPE_ACCOUNT': kwargs.get('stripe_account')})

                except stripe.error.StripeErrorWithParamCode as err:
                    # If the card is declined, Stripe will record a failed
                    # ``Charge`` and raise an exception here. Unfortunately only
                    # the Charge id is present in the CardError exception.
                    # So instead of generating
                    # an HTTP retrieve and recording a failed charge in our
                    # database, we raise and rollback.
                    raise CardError(str(err), err.code,
                        charge_processor_key=err.json_body['error']['charge'],
                        backend_except=err)
                except (stripe.error.AuthenticationError,
                        stripe.error.PermissionError) as err:
                    # It is possible we no longer have access to the connected
                    # account.
                    with transaction.atomic():
                        # We want this update to be committed even
                        # if other transactions are unwind on the exception.
                        provider.processor_pub_key = None
                        provider.processor_priv_key = None
                        provider.processor_deposit_key = None
                        provider.processor_refresh_token = None
                        provider.save()
                    raise ProcessorSetupError(
                        _("access to %(organization)s Stripe account was"\
                          " denied (access might have been revoked).") % {
                        'organization': provider}, provider, backend_except=err)

        except stripe.error.StripeErrorWithParamCode as err:
            raise CardError(str(err), err.code, backend_except=err)
        except (stripe.error.AuthenticationError,
                stripe.error.PermissionError) as err:
            raise ProcessorSetupError(
                _("Invalid request on processor for %(organization)s") % {
                'organization': provider}, provider, backend_except=err)
        except stripe.error.StripeError as err:
            LOGGER.exception(err)
            raise ProcessorError(str(err), backend_except=err)

        return context


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
                except stripe.error.StripeErrorWithParamCode as err:
                    raise CardError(str(err), err.code, backend_except=err)
                except stripe.error.AuthenticationError as err:
                    raise ProcessorSetupError(
                        _("Invalid request on processor for %(organization)s") %
                        {'organization': provider}, provider,
                        backend_except=err)
                except stripe.error.StripeError as err:
                    LOGGER.exception(err)
                    raise ProcessorError(str(err), backend_except=err)

        except ProcessorError:
            # OK here. We don't have a connected Stripe account.
            context.update({
                'balance_amount': "N/A",
                'balance_unit':  "N/A"})
        return context

    def _retrieve_card(self, subscriber, broker=None, stripe_customer=None):
        context = {}
        try:
            kwargs = self._prepare_charge_request(broker)
            if not stripe_customer:
                if subscriber.processor_card_key:
                    try:
                        stripe_customer = stripe.Customer.retrieve(
                            subscriber.processor_card_key,
                            expand=['invoice_settings.default_payment_method',
                                'default_source'],
                            **kwargs)
                    except stripe.error.StripeError as err:
                        LOGGER.exception("%s (mode=%s)", err,
                            "REMOTE" if kwargs else "LOCAL")
                        raise ProcessorError(str(err), backend_except=err)

            stripe_card = None
            if stripe_customer:
                if stripe_customer.invoice_settings.default_payment_method:
                    stripe_card = stripe_customer.invoice_settings\
                        .default_payment_method.card
                    billing_name = stripe_customer.invoice_settings\
                        .default_payment_method.billing_details.name
                elif stripe_customer.default_source:
                    # `default_payment_method` and `default_source` are not
                    # automatically in-sync on Stripe so we follow a smooth
                    # upgrade path here.
                    stripe_card = stripe_customer.default_source
                    billing_name = stripe_customer.default_source.name
                    try:
                        stripe.Customer.modify(subscriber.processor_card_key,
                            invoice_settings={
                               'default_payment_method': stripe_card},
                            **kwargs)
                    except stripe.error.StripeError as err:
                        LOGGER.exception("%s (mode=%s)", err,
                            "REMOTE" if kwargs else "LOCAL")
                        raise ProcessorError(str(err), backend_except=err)

            if stripe_card:
                last4 = '***-%s' % str(stripe_card.last4)
                exp_date = "%02d/%04d" % (
                    stripe_card.exp_month,
                    stripe_card.exp_year)
                context.update({
                    'last4': last4,
                    'exp_date': exp_date,
                    'card_name': billing_name
                })
        except ProcessorError:
            pass # OK here. We don't have a connected Stripe account.XXX really?
        return context

    def retrieve_card(self, subscriber, broker=None):
        return self._retrieve_card(subscriber, broker=broker)

    def retrieve_charge(self, charge):
        return self._update_charge_state(charge)

    def _update_charge_state(self, charge, stripe_charge=None, event_type=None):
        if stripe_charge is None:
            stripe_charge, _ = self._get_processor_charge(
                charge.processor_key, charge.broker)
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
            receipt_info = {
                'last4': stripe_charge.payment_method_details.card.last4,
                'exp_date': datetime.date(
                    stripe_charge.payment_method_details.card.exp_year,
                    stripe_charge.payment_method_details.card.exp_month, 1),
                'card_name': stripe_charge.billing_details.name
            }
            if event_type == 'charge.succeeded':
                if charge.is_progress:
                    charge.payment_successful(receipt_info=receipt_info)
                else:
                    LOGGER.warning(
                        "Already received a state update event for %s", charge)
            elif event_type == 'charge.failed':
                charge.failed(receipt_info=receipt_info)
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
        except stripe.error.StripeErrorWithParamCode as err:
            raise CardError(str(err), err.code, backend_except=err)
        except stripe.error.AuthenticationError as err:
            raise ProcessorSetupError(
                _("Invalid request on processor for %(organization)s") %
                {'organization': provider}, provider,
                backend_except=err)
        except stripe.error.StripeError as err:
            LOGGER.exception(err)
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
