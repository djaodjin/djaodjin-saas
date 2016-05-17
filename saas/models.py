#pylint: disable=too-many-lines

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

# Implementation Note:
#   The models and managers are declared in the same file to avoid messy
#   import loops.

"""
A billing profile (credit card and deposit bank account) is represented by
an ``Organization``.
An organization (subscriber) subscribes to services provided by another
organization (provider) through a ``Subscription`` to a ``Plan``.

There are no mechanism provided to authenticate as an ``Organization``.
Instead ``User`` authenticate with the application (through a login page
or an API token). They are then able to access URLs related
to an ``Organization`` based on their relation with that ``Organization``.
Two sets or relations are supported: managers and contributors (for details see
:doc:`Security <security>`).
"""

import datetime, hashlib, logging, random, re

from dateutil.relativedelta import relativedelta
from django.core.validators import MaxValueValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Max, Q, Sum
from django.db.models.query import QuerySet
from django.template.defaultfilters import slugify
from django.utils.http import quote
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.timezone import utc
from django.utils.translation import ugettext_lazy as _
from django_countries.fields import CountryField

from . import settings, signals
from .backends import get_processor_backend, ProcessorError, CardError
from .utils import (datetime_or_now, extract_full_exception_stack,
    generate_random_slug, get_roles, get_role_model)

from .humanize import (as_money, describe_buy_periods,
    DESCRIBE_BUY_PERIODS, DESCRIBE_BALANCE,
    DESCRIBE_CHARGED_CARD, DESCRIBE_CHARGED_CARD_PROCESSOR,
    DESCRIBE_CHARGED_CARD_PROVIDER, DESCRIBE_CHARGED_CARD_REFUND,
    DESCRIBE_DOUBLE_ENTRY_MATCH, DESCRIBE_LIABILITY_START_PERIOD,
    DESCRIBE_OFFLINE_PAYMENT)

LOGGER = logging.getLogger(__name__)

#pylint: disable=old-style-class,no-init


class InsufficientFunds(Exception):

    pass


class Price(object):

    def __init__(self, amount, unit):
        self.amount = amount
        self.unit = unit


class OrganizationManager(models.Manager):

    def create_organization(self, name, creation_time):
        creation_time = datetime.datetime.fromtimestamp(creation_time)
        billing_start = creation_time
        if billing_start.day > 28:
            # Insures that the billing cycle will be on the same day
            # every month.
            if billing_start.month >= 12:
                billing_start = datetime.datetime(billing_start.year + 1,
                    1, 1)
            else:
                billing_start = datetime.datetime(billing_start.year,
                    billing_start.month + 1, 1)
        customer = self.create(created_at=creation_time,
            slug=name, billing_start=billing_start)
        return customer

    def attached(self, user):
        """
        Returns the person ``Organization`` associated to the user or None
        in none can be reliably found.
        """
        from .compat import User
        if isinstance(user, User):
            username = user.username
        elif isinstance(user, basestring):
            username = user
        else:
            return None
        queryset = self.filter(slug=username)
        if queryset.exists():
            return queryset.get()
        return None

    def accessible_by(self, user):
        """
        Returns a QuerySet of Organziation which *user* has an associated
        role with.

        When *user* is a string instead of a ``User`` instance, it will
        be interpreted as a username.
        """
        from .compat import User
        if not isinstance(user, User):
            user = User.objects.get(username=user)
        return self.filter(pk__in=get_role_model().objects.filter(
            user=user).values('organization')).distinct()

    def with_role(self, user, role_name):
        """
        Returns a QuerySet of Organziation for which *user* has a *role_name*.
        """
        from .compat import User
        if not isinstance(user, User):
            user = User.objects.get(username=user)
        return self.filter(
            pk__in=get_roles(role_name).filter(user=user).values(
                'organization').distinct())

    def providers(self, subscriptions):
        """
        Set of ``Organization`` which provides the plans referenced
        by *subscriptions*.
        """
        if subscriptions:
            # Would be almost straightforward in a single raw SQL query
            # but expressing it for the Django compiler is not easy.
            selectors = set([])
            for subscription in subscriptions:
                selectors |= set([subscription.plan.organization.id])
            return self.filter(pk__in=selectors)
        return self.none()

    def providers_to(self, organization):
        """
        Set of ``Organization`` which provides active services
        to a subscribed *organization*.
        """
        return self.providers(Subscription.objects.filter(
            organization=organization))


class Organization(models.Model):
    """
    The Organization table stores information about who gets
    charged (and who gets paid) for using the service. Users can
    have one of two relationships with an Organization. They can
    either be managers (all permissions) or contributors (use permissions).
    """
    #pylint:disable=too-many-instance-attributes

    objects = OrganizationManager()
    slug = models.SlugField(unique=True,
        help_text=_("Unique identifier shown in the URL bar."))

    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_bulk_buyer = models.BooleanField(default=False,
        help_text=mark_safe('Enable GroupBuy (<a href="/docs/#group-billing"'\
' target="_blank">what is it?</a>)'))
    is_provider = models.BooleanField(default=False,
        help_text=_("Can fulfill the provider side of a subscription."))
    full_name = models.CharField(_('full name'), max_length=60, blank=True)
    # contact by e-mail
    email = models.EmailField(# XXX if we use unique=True here, the project
                              #     wizard must be changed.
    )
    # contact by phone
    phone = models.CharField(max_length=50)
    # contact by physical mail
    street_address = models.CharField(max_length=150)
    locality = models.CharField(max_length=50)
    region = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=50)
    country = CountryField()

    # Payment Processing
    # We could support multiple payment processors at the same time by
    # by having a relation to a separate table. For simplicity we only
    # allow on processor per organization at a time.
    subscriptions = models.ManyToManyField('Plan',
        related_name='subscribes', through='Subscription')
    billing_start = models.DateField(null=True, auto_now_add=True)

    funds_balance = models.PositiveIntegerField(default=0,
        help_text="Funds escrowed in cents")
    processor = models.ForeignKey('Organization', related_name='processes')
    processor_card_key = models.CharField(null=True, blank=True, max_length=20)
    processor_deposit_key = models.CharField(max_length=60, null=True,
        blank=True,
        help_text=_("Used to deposit funds to the organization bank account"))
    processor_priv_key = models.CharField(max_length=60, null=True, blank=True)
    processor_pub_key = models.CharField(max_length=60, null=True, blank=True)
    processor_refresh_token = models.CharField(max_length=60, null=True,
        blank=True)

    def __unicode__(self):
        return unicode(self.slug)

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if not self.slug:
            self.slug = slugify(self.full_name)
        if not self.processor_id: #pylint:disable=no-member
            self.processor = Organization.objects.get(pk=settings.PROCESSOR_ID)
        super(Organization, self).save(force_insert=force_insert,
             force_update=force_update, using=using,
             update_fields=update_fields)

    @property
    def printable_name(self):
        """
        Insures we can actually print a name visible on paper.
        """
        if self.full_name:
            return self.full_name
        return self.slug

    @property
    def has_profile_completed(self):
        return self.full_name and \
            self.email and \
            self.phone and \
            self.street_address and \
            self.locality and \
            self.region and \
            self.postal_code and \
            self.country

    @property
    def has_plan(self):
        return Plan.objects.filter(
            organization=self).count() > 0

    @property
    def has_bank_account(self):
        return self.processor_deposit_key

    @property
    def natural_interval(self):
        plan_periods = self.plans.values('interval').distinct()
        interval = Plan.MONTHLY
        if len(plan_periods) > 0:
            interval = Plan.YEARLY
            for period in plan_periods:
                interval = min(interval, period['interval'])
        return interval

    @property
    def natural_subscription_period(self):
        plan_periods = self.subscriptions.values('interval').distinct()
        interval = Plan.MONTHLY
        if len(plan_periods) > 0:
            interval = Plan.YEARLY
            for period in plan_periods:
                interval = min(interval, period['interval'])
        return Plan.get_natural_period(1, interval)

    @property
    def processor_backend(self):
        if not hasattr(self, '_processor_backend'):
            self._processor_backend = get_processor_backend(self)
        return self._processor_backend

    def add_role(self, user, role_name, at_time=None, reason=None):
        """
        Add user with a role to organization.
        """
        #pylint:disable=unused-argument
        # Implementation Note:
        # Django get_or_create will call router.db_for_write without
        # an instance so the using database will be lost. The following
        # code saves the relation in the correct database associated
        # with the organization.
        if role_name.endswith('s'):
            role_name = role_name[:-1]
        queryset = get_roles(role_name, using=self._state.db).filter(
            organization=self, user=user)
        if not queryset.exists():
            queryset = get_role_model().objects.db_manager(
                using=self._state.db).filter(organization=self, user=user,
                request_key__isnull=False)
            if queryset.exists():
                # We have a request. Let's use it.
                m2m = queryset.get()
                force_insert = False
            else:
                m2m = get_role_model()(organization=self, user=user)
                force_insert = True
            m2m.name = role_name
            m2m.request_key = None
            m2m.save(using=self._state.db, force_insert=force_insert)
            signals.user_relation_added.send(sender=__name__,
                organization=m2m.organization, user=m2m.user,
                role=m2m.name, reason=reason)
            return True
        return False

    def add_role_request(self, user, at_time=None, reason=None):
        if not get_role_model().objects.filter(
                organization=self, user=user).exists():
            # Otherwise a role already exists
            # or a request was previously sent.
            at_time = datetime_or_now(at_time)
            salt = hashlib.sha1(str(random.random())).hexdigest()[:5]
            m2m = get_role_model()(created_at=at_time,
                organization=self, user=user,
                request_key=hashlib.sha1(salt+user.username).hexdigest())
            m2m.save(using=self._state.db, force_insert=True)
            signals.user_relation_requested.send(sender=__name__,
                organization=self, user=user, reason=reason)

    def add_manager(self, user, at_time=None, reason=None):
        """
        Add user as a manager to organization.
        """
        #pylint: disable=unused-argument
        return self.add_role(user, settings.MANAGER,
            at_time=at_time, reason=reason)

    def remove_role(self, user, role_name):
        """
        Remove user as a *role_name* (ex: manager, contributor) to organization.
        """
        relation = get_roles(role_name).get(organization=self, user=user)
        relation.delete()

    def with_role(self, role_name):
        """
        Returns all users with a *role_name* to organization.
        """
        from .compat import User
        return User.objects.filter(
            pk__in=get_roles(role_name).filter(organization=self).values(
                'user')).distinct()

    def receivables(self):
        """
        Returns all ``Transaction`` for a *provider* whose *orig_account*
        is ``RECEIVABLE``.
        """
        return Transaction.objects.filter(
            orig_organization=self,
            orig_account=Transaction.RECEIVABLE)

    def update_bank(self, bank_token):
        if bank_token is None:
            self.processor_deposit_key = None
            self.processor_priv_key = None
            self.processor_pub_key = None
            self.processor_refresh_token = None
            self.save()
        else:
            self.processor_backend.update_bank(self, bank_token)
            LOGGER.info('Updated bank information for %s on processor '\
                '{"processor_deposit_key": %s}',
                self, self.processor_deposit_key)
        signals.bank_updated.send(self)

    def update_card(self, card_token, user):
        self.processor_backend.create_or_update_card(
            self, card_token, user=user, broker=get_broker())
        LOGGER.info('Updated card information for %s on processor '\
            '{"processor_card_key": %s}', self, self.processor_card_key)

    @method_decorator(transaction.atomic)
    def checkout(self, invoicables, user, token=None, remember_card=True):
        """
        *invoiced_items* is a set of ``Transaction`` that will be recorded
        in the ledger. Associated subscriptions will be updated such that
        the ends_at is extended in the future.
        """
        #pylint: disable=too-many-locals, too-many-statements
        claim_carts = {}
        invoiced_items = []
        new_organizations = []
        coupon_providers = set([])
        for invoicable in invoicables:
            subscription = invoicable['subscription']
            # If the invoicable we are checking out is somehow related to
            # a user shopping cart, we mark that cart item as recorded
            # unless the organization does not exist in the database,
            # in which case we will create a claim_code for it.
            cart_item = None
            cart_items = CartItem.objects.get_cart(user, plan=subscription.plan)
            if cart_items.exists():
                bulk_items = cart_items.filter(
                    email=subscription.organization.email)
                if bulk_items.exists():
                    cart_item = bulk_items.get()
                else:
                    cart_item = cart_items.get()

            if not subscription.organization.id:
                # When the organization does not exist into the database,
                # we will create a random (i.e. hard to guess) claim code
                # that will be emailed to the expected subscriber.
                key = subscription.organization.email
                if not key in new_organizations:
                    claim_carts[key] = []
                    new_organizations += [subscription.organization]
                    coupon_providers |= set([subscription.provider])
                assert cart_item is not None
                claim_carts[key] += [cart_item]
            else:
                LOGGER.info("[checkout] save subscription of %s to %s",
                    subscription.organization, subscription.plan)
                subscription.save()
                if cart_item:
                    cart_item.recorded = True
                    cart_item.save()

        # At this point we have gathered all the ``Organization``
        # which have yet to be registered. For these no ``Subscription``
        # has been created yet. We create a claim_code that will
        # be emailed to the expected subscribers such that it will populate
        # their cart automatically.
        coupons = {}
        claim_codes = {}
        for provider in coupon_providers:
            coupon = Coupon.objects.create(
                code='cpn_%s' % generate_random_slug(),
                organization=provider,
                percent=100, nb_attempts=0,
                description=('Auto-generated after payment by %s'
                    % self.printable_name))
            LOGGER.info('Auto-generated Coupon %s for %s',
                coupon.code, provider)
            coupons.update({provider.id: coupon})
        for key, cart_items in claim_carts.iteritems():
            claim_code = generate_random_slug()
            provider = CartItem.objects.provider(cart_items)
            for cart_item in cart_items:
                cart_item.email = ''
                cart_item.user = None
                cart_item.first_name = ''
                cart_item.claim_code = claim_code
                cart_item.last_name = self.printable_name
                cart_item.coupon = coupons[cart_item.plan.organization.id]
                cart_item.save()
            LOGGER.info("Generated claim code '%s' for %d cart items",
                claim_code, len(cart_items))
            claim_codes.update({key: claim_code})

        # We now either have a ``subscription.id`` (subscriber present
        # in the database) or a ``Coupon`` (subscriber absent from
        # the database).
        for invoicable in invoicables:
            subscription = invoicable['subscription']
            if subscription.id:
                event_id = subscription.id
            else:
                # We do not use id's here. Integers are reserved
                # to match ``Subscription.id``.
                coupon = coupons[subscription.provider.id]
                event_id = coupon.code
            for invoiced_item in invoicable['lines']:
                invoiced_item.event_id = event_id
                invoiced_items += [invoiced_item]

        invoiced_items = Transaction.objects.execute_order(invoiced_items, user)
        charge = Charge.objects.charge_card(self, invoiced_items, user,
            token=token, remember_card=remember_card)

        # We email users which have yet to be registerd after the charge
        # is created, just that we don't inadvertently email new subscribers
        # in case something goes wrong.
        for organization in new_organizations:
            signals.claim_code_generated.send(
                sender=__name__, subscriber=organization,
                claim_code=claim_codes[organization.email], user=user)

        return charge

    def get_deposit_context(self):
        return self.processor_backend.get_deposit_context()

    def retrieve_bank(self):
        """
        Returns associated bank account as a dictionnary.
        """
        context = self.processor_backend.retrieve_bank(self)
        processor_amount = context.get('balance_amount', 0)
        balance = Transaction.objects.get_balance(
            organization=self, account=Transaction.FUNDS)
        available_amount = min(balance['amount'], processor_amount)
        transfer_fee = self.processor_backend.prorate_transfer(
            processor_amount, self)
        if available_amount > transfer_fee:
            available_amount -= transfer_fee
        else:
            available_amount = 0
        context.update({'balance_amount': available_amount})
        return context

    def retrieve_card(self):
        """
        Returns associated credit card.
        """
        return self.processor_backend.retrieve_card(self, broker=get_broker())

    def get_transfers(self):
        """
        Returns a ``QuerySet`` of ``Transaction`` after it has been
        reconcile with the withdrawals that happened in the processor
        backend.
        """
        queryset = Transaction.objects.filter(
            orig_organization=self,
            orig_account=Transaction.FUNDS,
            dest_account__startswith=Transaction.WITHDRAW).order_by(
                'created_at')
        created_at = queryset.values('created_at').first()
        if isinstance(created_at, dict):
            created_at = created_at.get('created_at', None)
        else:
            created_at = None
        self.processor_backend.reconcile_transfers(self, created_at)
        return Transaction.objects.by_organization(self)

    def withdraw_funds(self, amount, user):
        if amount == 0:
            # Nothing to do.
            return
        descr = "withdraw from %s" % self.printable_name
        if user:
            descr += ' (%s)' % user.username
        self.processor_backend.create_transfer(
            self, amount, currency='usd', descr=descr)
        # We will wait on a call to ``reconcile_transfers`` to create
        # those ``Trnansaction`` in the database.

    def create_withdraw_transactions(self, event_id, amount, unit, descr,
                                     created_at=None):
        """
        Withdraw funds from the site into the provider's bank account.

        We record one straightforward ``Transaction`` for the withdrawal
        and an additional one in case there is a processor transfer fee::

            yyyy/mm/dd withdrawal to provider bank account
                processor:Withdraw                       amount
                provider:Funds

            yyyy/mm/dd processor fee paid by provider (Stripe: 25 cents)
                processor:Funds                          processor_fee
                provider:Funds

        Example::

            2014/09/10 withdraw from cowork
                stripe:Withdraw                          $174.52
                cowork:Funds

            2014/09/10 transfer fee to Stripe
                stripe:Funds                               $0.25
                cowork:Funds
        """
        #pylint:disable=too-many-arguments
        # We use ``get_or_create`` here because the method is also called
        # when transfers are reconciled with the payment processor.
        with transaction.atomic():
            if amount > 0:
                _, created = Transaction.objects.get_or_create(
                    event_id=event_id,
                    descr=descr,
                    created_at=created_at,
                    dest_unit=unit,
                    dest_amount=amount,
                    dest_account=Transaction.WITHDRAW,
                    dest_organization=self.processor,
                    orig_unit=unit,
                    orig_amount=amount,
                    orig_account=Transaction.FUNDS,
                    orig_organization=self)
            elif amount < 0:
                # When there is not enough funds in the Stripe account,
                # Stripe will draw back from the bank account to cover
                # a refund, etc.

                _, created = Transaction.objects.get_or_create(
                    event_id=event_id,
                    descr=descr,
                    created_at=created_at,
                    dest_unit=unit,
                    dest_amount=- amount,
                    dest_account=Transaction.FUNDS,
                    dest_organization=self,
                    orig_unit=unit,
                    orig_amount=- amount,
                    orig_account=Transaction.WITHDRAW,
                    orig_organization=self.processor)
            if created:
                # Add processor fee for transfer.
                transfer_fee = self.processor_backend.prorate_transfer(
                    amount, self)
                self.create_processor_fee(transfer_fee, Transaction.FUNDS,
                    event_id=event_id, created_at=created_at)
                self.funds_balance -= amount
                self.save()

    def create_processor_fee(self, fee_amount, processor_account,
                             event_id=None, created_at=None, descr=None):
        #pylint: disable=too-many-arguments
        if fee_amount:
            funds_unit = 'usd' # XXX currency on receipient bank account
            created_at = datetime_or_now(created_at)
            if not descr:
                descr = 'Processor fee'
            if event_id:
                descr += ' for %s' % str(event_id)
            Transaction.objects.create(
                event_id=event_id,
                descr=descr,
                created_at=created_at,
                dest_unit=funds_unit,
                dest_amount=fee_amount,
                dest_account=processor_account,
                dest_organization=self.processor,
                orig_unit=funds_unit,
                orig_amount=fee_amount,
                orig_account=Transaction.FUNDS,
                orig_organization=self)
        self.funds_balance -= fee_amount
        self.save()


class Role(models.Model):

    created_at = models.DateTimeField(auto_now_add=True)
    organization = models.ForeignKey(Organization)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='user_id')
    name = models.CharField(max_length=20)
    request_key = models.CharField(null=True, max_length=40)
    grant_key = models.CharField(null=True, max_length=40)

    class Meta:
        unique_together = ('name', 'organization', 'user')

    def __unicode__(self):
        return '%s-%s-%s' % (
            self.name, unicode(self.organization), unicode(self.user))


class Agreement(models.Model):

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=150, unique=True)
    modified = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return unicode(self.slug)


class SignatureManager(models.Manager):

    def create_signature(self, agreement, user):
        if isinstance(agreement, basestring):
            #pylint: disable=no-member
            agreement = Agreement.objects.db_manager(self.db).get(
                slug=agreement)
        try:
            sig = self.get(agreement=agreement, user=user)
            sig.last_signed = datetime_or_now()
            sig.save()
        except Signature.DoesNotExist:
            sig = self.create(agreement=agreement, user=user)
        return sig

    def has_been_accepted(self, agreement, user):
        if isinstance(agreement, basestring):
            agreement = Agreement.objects.get(slug=agreement)
        try:
            sig = self.get(agreement=agreement, user=user)
            if sig.last_signed < agreement.modified:
                return False
        except Signature.DoesNotExist:
            return False
        return True


class Signature(models.Model):

    objects = SignatureManager()

    last_signed = models.DateTimeField(auto_now_add=True)
    agreement = models.ForeignKey(Agreement)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='user_id',
        related_name='signatures')

    class Meta:
        unique_together = ('agreement', 'user')

    def __unicode__(self):
        return '%s-%s' % (self.user, self.agreement)


class ChargeManager(models.Manager):

    def create_charge(self, customer, transactions, amount, unit,
                      processor, processor_charge_id, last4, exp_date,
                      descr=None, created_at=None):
        #pylint: disable=too-many-arguments
        created_at = datetime_or_now(created_at)
        with transaction.atomic():
            charge = self.create(
                processor=processor, processor_key=processor_charge_id,
                amount=amount, unit=unit,
                created_at=created_at, description=descr,
                customer=customer, last4=last4, exp_date=exp_date)
            for invoiced in transactions:
                ChargeItem.objects.create(invoiced=invoiced, charge=charge)
            LOGGER.info('{"event": "charge_created", "charge": "%s",'\
                ' "organization": "%s", "amount": %d, "unit": "%s"}',
                charge.processor_key, customer, charge.amount, charge.unit)
        return charge

    def charge_card(self, customer, transactions, descr=None,
                    user=None, token=None, remember_card=True):
        #pylint: disable=too-many-arguments
        charge = None
        balance = sum_dest_amount(transactions)
        amount = balance['amount']
        if amount == 0:
            return charge
        for invoice_items in Transaction.objects.by_processor_key(
                transactions).values():
            # XXX This is only working if all line items use the same
            # provider keys to record the charge.
            charge = self.charge_card_one_processor(
                customer, invoice_items, descr=descr,
                user=user, token=token, remember_card=remember_card)
        return charge

    def charge_card_one_processor(self, customer, transactions, descr=None,
                    user=None, token=None, remember_card=True):
        #pylint: disable=too-many-arguments,too-many-locals
        """
        Create a charge on a customer card.

        Be careful, Stripe will not processed charges less than 50 cents.
        """
        balance = sum_dest_amount(transactions)
        amount = balance['amount']
        unit = balance['unit']
        if amount == 0:
            return None
        providers = Transaction.objects.providers(transactions)
        if len(providers) == 1:
            broker = providers[0]
        else:
            broker = get_broker()
        processor = broker.processor
        processor_backend = broker.processor_backend
        descr = DESCRIBE_CHARGED_CARD % {
            'charge': '', 'organization': customer.printable_name}
        if user:
            descr += ' (%s)' % user.username
        try:
            if token:
                if remember_card:
                    customer.update_card(token, user)
                    (processor_charge_id, created_at,
                     last4, exp_date) = processor_backend.create_charge(
                         customer, amount, unit,
                         broker=broker, descr=descr)
                else:
                    (processor_charge_id, created_at,
                     last4, exp_date) = processor_backend.create_charge_on_card(
                         token, amount, unit,
                         broker=broker, descr=descr)
            else:
                # XXX A card must already be attached to the customer.
                (processor_charge_id, created_at,
                 last4, exp_date) = processor_backend.create_charge(
                     customer, amount, unit,
                     broker=broker, descr=descr)
            # Create record of the charge in our database
            descr = DESCRIBE_CHARGED_CARD % {'charge': processor_charge_id,
                'organization': customer.printable_name}
            if user:
                descr += ' (%s)' % user.username
            charge = self.create_charge(customer, transactions, amount, unit,
                processor, processor_charge_id, last4, exp_date,
                descr=descr, created_at=created_at)
        except CardError as err:
            # Expected runtime error. We just log that the charge was declined.
            LOGGER.info('{"event": "CardError",'\
                ' "amount": %d, "customer": "%s", "msg": "%s"}',
                amount, customer, err.processor_details())
            raise
        except ProcessorError as err:
            # An error from the processor which indicates the logic might be
            # incorrect, the network down, etc. We want to know about it right
            # away.
            LOGGER.error("ProcessorError for charge of %d cents to %s\n" % (
                amount, customer) + extract_full_exception_stack(err))
            raise
        return charge


class Charge(models.Model):
    """
    Keep track of charges that have been emitted by the app.
    We save the last4 and expiration date so we are able to present
    a receipt.
    """
    CREATED = 0
    DONE = 1
    FAILED = 2
    DISPUTED = 3
    CHARGE_STATES = {
        (CREATED, 'created'),
        (DONE, 'done'),
        (FAILED, 'failed'),
        (DISPUTED, 'disputed')
    }

    objects = ChargeManager()

    created_at = models.DateTimeField(auto_now_add=True)
    amount = models.PositiveIntegerField(default=0, help_text="Amount in cents")
    unit = models.CharField(max_length=3, default='usd')
    customer = models.ForeignKey(Organization,
        help_text='organization charged')
    description = models.TextField(null=True)
    last4 = models.PositiveSmallIntegerField()
    exp_date = models.DateField()
    processor = models.ForeignKey('Organization', related_name='charges')
    processor_key = models.SlugField(unique=True, db_index=True)
    state = models.PositiveSmallIntegerField(
        choices=CHARGE_STATES, default=CREATED)

    # XXX unique together paid and invoiced.
    # customer and invoiced_items account payble should match.

    def __unicode__(self):
        return unicode(self.processor_key)

    @property
    def price(self):
        return Price(self.amount, self.unit)

    @property
    def state_string(self):
        return self.get_state_display()

    @property
    def line_items(self):
        """
        In most cases, use the ``line_items`` property instead of
        the ``charge_items`` because the order in which the records
        are returned is not guarenteed by SQL.
        This is important when identifying line items by an index.
        """
        return self.charge_items.order_by('id')

    @property
    def processor_backend(self):
        if not hasattr(self, '_processor_backend'):
            #pylint:disable=no-member
            self._processor_backend = self.broker.processor_backend
        return self._processor_backend

    @property
    def invoiced_total_amount(self):
        """
        Returns the total amount of all invoiced items.
        """
        balance = sum_dest_amount(Transaction.objects.filter(
            invoiced_item__charge=self))
        amount = balance['amount']
        unit = balance['unit']
        return amount, unit

    @property
    def is_disputed(self):
        return self.state == self.DISPUTED

    @property
    def is_failed(self):
        return self.state == self.FAILED

    @property
    def is_paid(self):
        return self.state == self.DONE

    @property
    def is_progress(self):
        return self.state == self.CREATED

    @property
    def refunded(self):
        """
        All ``Transaction`` which are part of a refund for this ``Charge``.
        """
        return Transaction.objects.by_charge(self).filter(
            orig_account=Transaction.REFUNDED)

    def capture(self):
        # XXX Create transaction
        signals.charge_updated.send(sender=__name__, charge=self, user=None)

    @property
    def broker(self):
        """
        All the invoiced items on this charge must be related to the same
        broker ``Organization``.
        """
        #pylint: disable=no-member
        providers = Transaction.objects.providers([charge_item.invoiced
            for charge_item in self.charge_items.all()])
        assert len(providers) <= 1
        if len(providers) == 0:
            return []
        return providers[0]

    def dispute_created(self):
        #pylint: disable=too-many-locals
        self.state = self.DISPUTED
        created_at = datetime_or_now()
        balance = sum_orig_amount(self.refunded)
        previously_refunded = balance['amount']
        refund_available = self.amount - previously_refunded
        charge_available_amount, provider_unit, \
            charge_fee_amount, processor_unit \
            = self.processor_backend.charge_distribution(self)
        corrected_available_amount = charge_available_amount
        corrected_fee_amount = charge_fee_amount
        with transaction.atomic():
            providers = set([])
            for charge_item in self.line_items:
                refunded_amount = min(refund_available,
                    charge_item.invoiced_item.dest_amount)
                provider = charge_item.invoiced_item.orig_organization
                if not provider in providers:
                    provider.create_processor_fee(
                        self.processor_backend.dispute_fee(self.amount),
                        Transaction.CHARGEBACK,
                        event_id=self.id, created_at=created_at)
                    providers |= set([provider])
                charge_item.create_refund_transactions(
                    refunded_amount,
                    charge_available_amount, charge_fee_amount,
                    corrected_available_amount, corrected_fee_amount,
                    created_at=created_at, provider_unit=provider_unit,
                    processor_unit=processor_unit,
                    refund_type=Transaction.CHARGEBACK)
                refund_available -= refunded_amount
            self.save()
        signals.charge_updated.send(sender=__name__, charge=self, user=None)

    def dispute_updated(self):
        self.state = self.DISPUTED
        self.save()
        signals.charge_updated.send(sender=__name__, charge=self, user=None)

    def dispute_lost(self):
        self.state = self.DONE
        self.save()
        signals.charge_updated.send(sender=__name__, charge=self, user=None)

    def dispute_won(self):
        self.state = self.DONE
        with transaction.atomic():
            for reverted in Transaction.objects.by_charge(self).filter(
                    dest_account=Transaction.CHARGEBACK):
                Transaction.objects.create(
                    event_id=reverted.event_id,
                    descr='%s - reverted' % reverted.descr,
                    created_at=reverted.created_at,
                    dest_unit=reverted.orig_unit,
                    dest_amount=reverted.orig_amount,
                    dest_account=reverted.orig_account,
                    dest_organization=reverted.orig_organization,
                    orig_unit=reverted.dest_unit,
                    orig_amount=reverted.dest_amount,
                    orig_account=reverted.dest_account,
                    orig_organization=reverted.dest_organization)
            self.save()
        signals.charge_updated.send(sender=__name__, charge=self, user=None)

    def failed(self):
        self.state = self.FAILED
        self.save()
        signals.charge_updated.send(sender=__name__, charge=self, user=None)


    @method_decorator(transaction.atomic)
    def payment_successful(self):
        """
        When a charge through the payment processor is sucessful,
        a unique ``Transaction`` records the charge through the processor.
        The amount of the charge is then redistributed to the providers
        (minus processor fee)::

            ; Record the charge

            yyyy/mm/dd charge event
                processor:Funds                          charge_amount
                subscriber:Liability

            ; Compensate for atomicity of charge record (when necessary)

            yyyy/mm/dd invoiced-item event
                subscriber:Liability           min(invoiced_item_amount,
                subscriber:Payable                      balance_payable)

            ; Distribute processor fee and funds to the provider

            yyyy/mm/dd processor fee paid by provider
                provider:Expenses                        processor_fee
                processor:Backlog

            yyyy/mm/dd distribution to provider (backlog accounting)
                provider:Receivable                      plan_amount
                provider:Backlog

            yyyy/mm/dd distribution to provider
                provider:Funds                           distribute_amount
                processor:Funds

        Example::

            2014/09/10 Charge ch_ABC123 on credit card of xia
                stripe:Funds                           $179.99
                xia:Liability

            2014/09/10 Keep a balanced ledger
                xia:Liability                          $179.99
                xia:Payable

            2014/09/10 Charge ch_ABC123 processor fee for open-space
                cowork:Expenses                         $5.22
                stripe:Backlog

            2014/09/10 Charge ch_ABC123 distribution for open-space
                cowork:Receivable                     $189.00
                cowork:Backlog

            2014/09/10 Charge ch_ABC123 distribution for open-space
                cowork:Funds                          $174.77
                stripe:Funds
        """
        #pylint: disable=too-many-locals
        assert self.state == self.CREATED

        # Example:
        # 2014/01/15 charge on xia card
        #     stripe:Funds                                 15800
        #     xia:Liability
        total_distribute_amount, funds_unit, \
            total_fee_amount, processor_funds_unit \
            = self.processor_backend.charge_distribution(self)

        charge_transaction = Transaction.objects.create(
            event_id=self.id,
            descr=self.description,
            created_at=self.created_at,
            dest_unit=self.unit,
            # XXX provider and processor must have same units.
            dest_amount=self.amount,
            dest_account=Transaction.FUNDS,
            dest_organization=self.processor,
            orig_unit=self.unit,
            orig_amount=self.amount,
            orig_account=Transaction.LIABILITY,
            orig_organization=self.customer)
        # Once we have created a transaction for the charge, let's
        # redistribute the funds to their rightful owners.
        for charge_item in self.charge_items.all(): #pylint: disable=no-member
            invoiced_item = charge_item.invoiced

            # If there is still an amount on the ``Payable`` account,
            # we create Payable to Liability transaction in order to correct
            # the accounts amounts. This is a side effect of the atomicity
            # requirement for a ``Transaction`` associated to a ``Charge``.
            balance = Transaction.objects.get_event_balance(
                invoiced_item.event_id, account=Transaction.PAYABLE)
            balance_payable = balance['amount']
            if balance_payable > 0:
                available = min(invoiced_item.dest_amount, balance_payable)
                # Example:
                # 2014/01/15 keep a balanced ledger
                #     xia:Liability                                 15800
                #     xia:Payable
                Transaction.objects.create(
                    event_id=invoiced_item.event_id,
                    created_at=self.created_at,
                    descr=DESCRIBE_DOUBLE_ENTRY_MATCH,
                    dest_unit=invoiced_item.dest_unit,
                    dest_amount=available,
                    dest_account=Transaction.LIABILITY,
                    dest_organization=invoiced_item.dest_organization,
                    orig_unit=invoiced_item.dest_unit,
                    orig_amount=available,
                    orig_account=Transaction.PAYABLE,
                    orig_organization=invoiced_item.dest_organization)

            # XXX used for provider and in description.
            event = invoiced_item.get_event()
            provider = event.provider
            orig_item_amount = invoiced_item.dest_amount
            # Has long as we have only one item and charge/funds are using
            # same unit, multiplication and division are carefully crafted
            # to keep full precision.
            # XXX to check with transfer btw currencies and multiple items.
            orig_fee_amount = (orig_item_amount *
                total_fee_amount / (total_distribute_amount + total_fee_amount))
            orig_distribute_amount = orig_item_amount - orig_fee_amount
            fee_amount = ((total_fee_amount * orig_item_amount / self.amount))
            distribute_amount = (
                total_distribute_amount * orig_item_amount / self.amount)
            LOGGER.debug("payment_successful(charge=%s) distribute: %d %s, "\
                "fee: %d %s out of total distribute: %d %s, total fee: %d %s",
                self.processor_key, distribute_amount, funds_unit,
                fee_amount, processor_funds_unit,
                total_distribute_amount, funds_unit,
                total_fee_amount, processor_funds_unit)
            if fee_amount > 0:
                # Example:
                # 2014/01/15 fee to cowork
                #     cowork:Expenses                             900
                #     stripe:Backlog
                charge_item.invoiced_fee = Transaction.objects.create(
                    created_at=self.created_at,
                    descr=DESCRIBE_CHARGED_CARD_PROCESSOR % {
                        'charge': self.processor_key, 'event': event},
                    event_id=self.id,
                    dest_unit=funds_unit,
                    dest_amount=fee_amount,
                    dest_account=Transaction.EXPENSES,
                    dest_organization=provider,
                    orig_unit=self.unit,
                    orig_amount=orig_fee_amount,
                    orig_account=Transaction.BACKLOG,
                    orig_organization=self.processor)
                # pylint:disable=no-member
                self.processor.funds_balance += fee_amount
                self.processor.save()

            # Example:
            # 2014/01/15 distribution due to cowork
            #     cowork:Receivable                             8000
            #     cowork:Backlog
            #
            # 2014/01/15 distribution due to cowork
            #     cowork:Funds                                  7000
            #     stripe:Funds
            Transaction.objects.create(
                event_id=event.id,
                created_at=self.created_at,
                descr=DESCRIBE_CHARGED_CARD_PROVIDER % {
                        'charge': self.processor_key, 'event': event},
                dest_unit=self.unit,
                dest_amount=orig_item_amount,
                dest_account=Transaction.RECEIVABLE,
                dest_organization=provider,
                orig_unit=funds_unit,
                # XXX Just making sure we don't screw up rounding
                # when using the same unit.
                orig_amount=(distribute_amount + fee_amount
                    if self.unit != funds_unit else orig_item_amount),
                orig_account=Transaction.BACKLOG,
                orig_organization=provider)

            charge_item.invoiced_distribute = Transaction.objects.create(
                event_id=self.id,
                created_at=self.created_at,
                descr=DESCRIBE_CHARGED_CARD_PROVIDER % {
                        'charge': self.processor_key, 'event': event},
                dest_unit=funds_unit,
                dest_amount=distribute_amount,
                dest_account=Transaction.FUNDS,
                dest_organization=provider,
                orig_unit=self.unit,
                orig_amount=orig_distribute_amount,
                orig_account=Transaction.FUNDS,
                orig_organization=self.processor)
            charge_item.save()
            provider.funds_balance += distribute_amount
            provider.save()

        invoiced_amount, _ = self.invoiced_total_amount
        if invoiced_amount > self.amount:
            #pylint: disable=nonstandard-exception
            raise IntegrityError("The total amount of invoiced items for "\
              "charge %s exceed the amount of the charge.", self.processor_key)

        self.state = self.DONE
        self.save()

        signals.charge_updated.send(sender=__name__, charge=self, user=None)
        return charge_transaction

    def refund(self, linenum, refunded_amount=None, created_at=None, user=None):
        # XXX We donot currently supply a *description* for the refund.
        #pylint:disable=too-many-locals
        assert self.state == self.DONE

        # We do all computation and checks before starting to modify
        # the database to minimize the chances of getting into
        # an inconsistent state.
        #pylint: disable=no-member
        charge_item = self.line_items[linenum]
        invoiced_item = charge_item.invoiced
        if refunded_amount is None:
            refunded_amount = invoiced_item.dest_amount

        balance = sum_orig_amount(self.refunded)
        previously_refunded = balance['amount']
        refund_available = min(invoiced_item.dest_amount,
                               self.amount - previously_refunded)
        if refunded_amount > refund_available:
            raise InsufficientFunds("Cannot refund %(refund_required)s"\
" while there is only %(refund_available)s available on the line item."
% {'refund_available': as_money(refund_available, self.unit),
   'refund_required': as_money(refunded_amount, self.unit)})

        charge_available_amount, provider_unit, \
            charge_fee_amount, processor_unit \
            = self.processor_backend.charge_distribution(
                self, refunded=previously_refunded)

        # We execute the refund on the processor backend here such that
        # the following call to ``processor_backend.charge_distribution``
        # returns the correct ``corrected_available_amount`` and
        # ``corrected_fee_amount``.
        self.processor_backend.refund_charge(self, refunded_amount)

        corrected_available_amount, provider_unit, \
            corrected_fee_amount, processor_unit \
            = self.processor_backend.charge_distribution(
                self, refunded=previously_refunded + refunded_amount)

        charge_item.create_refund_transactions(refunded_amount,
            charge_available_amount, charge_fee_amount,
            corrected_available_amount, corrected_fee_amount,
            created_at=created_at,
            provider_unit=provider_unit, processor_unit=processor_unit)
        LOGGER.info('refund {"charge": "%s", "linenum": "%s", "amount": "%d"}',
            self, linenum, refunded_amount)
        signals.charge_updated.send(sender=__name__, charge=self, user=user)

    def retrieve(self):
        """
        Retrieve the state of charge from the processor.
        """
        self.processor_backend.retrieve_charge(self)
        return self


class ChargeItem(models.Model):
    """
    Keep track of each item invoiced within a ``Charge``.
    """
    charge = models.ForeignKey(Charge, related_name='charge_items')
    # XXX could be a ``Subscription`` or a balance.
    invoiced = models.ForeignKey('Transaction', related_name='invoiced_item',
        help_text="transaction invoiced through this charge")
    invoiced_fee = models.ForeignKey('Transaction', null=True,
        related_name='invoiced_fee_item',
        help_text="fee transaction to process the transaction invoiced"\
" through this charge")
    invoiced_distribute = models.ForeignKey('Transaction', null=True,
        related_name='invoiced_distribute',
        help_text="transaction recording the distribution from processor"\
" to provider.")

    class Meta:
        unique_together = ('charge', 'invoiced')

    def __unicode__(self):
        return '%s-%s' % (unicode(self.charge), unicode(self.invoiced))

    @property
    def refunded(self):
        """
        All ``Transaction`` which are part of a refund for this ``ChargeItem``.
        """
        return Transaction.objects.filter(
            event_id=str(self.id), orig_account=Transaction.REFUNDED)

    def create_refund_transactions(self, refunded_amount,
        charge_available_amount, charge_fee_amount,
        corrected_available_amount, corrected_fee_amount,
        created_at=None, provider_unit=None, processor_unit=None,
        refund_type=None):
        """
        Each ``ChargeItem`` can be partially refunded::

            yyyy/mm/dd refund to subscriber
                provider:Refund                          refunded_amount
                subscriber:Refunded

            yyyy/mm/dd refund of processor fee
                processor:Refund                         processor_fee
                processor:Funds

            yyyy/mm/dd refund of processor fee
                processor:Refund                         distribute_amount
                provider:Funds

        ``Refund`` is replaced by ``Chargeback`` if the refund was initiated
        by a chargeback event.

        Example::

            2014/09/10 Charge ch_ABC123 refund for subscribe to open-space plan
                cowork:Refund                            $179.99
                xia:Refunded

            2014/09/10 Charge ch_ABC123 refund processor fee
                stripe:Refund                              $5.22
                stripe:Funds

            2014/09/10 Charge ch_ABC123 cancel distribution
                stripe:Refund                            $174.77
                cowork:Funds
        """
        #pylint:disable=too-many-locals,too-many-arguments,no-member
        created_at = datetime_or_now(created_at)
        if not refund_type:
            refund_type = Transaction.REFUND
        charge = self.charge
        processor = charge.processor
        invoiced_item = self.invoiced
        invoiced_fee = self.invoiced_fee
        provider = invoiced_item.orig_organization
        customer = invoiced_item.dest_organization
        invoiced_distribute = self.invoiced_distribute
        if not processor_unit:
            processor_unit = 'usd' # XXX
        if not provider_unit:
            provider_unit = 'usd' # XXX
        refunded_fee_amount = 0
        if invoiced_fee:
            refunded_fee_amount = min(
                charge_fee_amount - corrected_fee_amount,
                invoiced_fee.orig_amount)
        refunded_distribute_amount = \
            charge_available_amount - corrected_available_amount
        if invoiced_distribute:
            orig_distribute = "%d %s" % (invoiced_distribute.dest_amount,
                invoiced_distribute.dest_unit)
            refunded_distribute_amount = min(refunded_distribute_amount,
                invoiced_distribute.dest_amount)
        else:
            orig_distribute = 'N/A'
        # Implementation Note:
        # refunded_amount = refunded_distribute_amount + refunded_fee_amount

        LOGGER.debug(
            "create_refund_transactions(charge=%s, refund_amount=%d %s)"\
            " distribute: %d %s, fee: %d %s, available: %d %s, "\
            " orig_distribute: %s",
            charge.processor_key, refunded_amount, charge.unit,
            refunded_distribute_amount, provider_unit,
            refunded_fee_amount, processor_unit,
            charge_available_amount, charge.unit,
            orig_distribute)

        if refunded_distribute_amount > provider.funds_balance:
            raise InsufficientFunds(
                '%(provider)s has %(funds_available)s of funds available.'\
' %(funds_required)s are required to refund "%(descr)s"' % {
    'provider': provider,
    'funds_available': as_money(abs(provider.funds_balance), provider_unit),
    'funds_required': as_money(abs(refunded_distribute_amount), provider_unit),
    'descr': invoiced_item.descr})

        with transaction.atomic():
            # Record the refund from provider to subscriber
            descr = DESCRIBE_CHARGED_CARD_REFUND % {
                'charge': charge.processor_key,
                'refund_type': refund_type.lower(),
                'descr': invoiced_item.descr}
            Transaction.objects.create(
                event_id=self.id,
                descr=descr,
                created_at=created_at,
                dest_unit=provider_unit,
                dest_amount=refunded_distribute_amount + refunded_fee_amount,
                dest_account=refund_type,
                dest_organization=provider,
                orig_unit=charge.unit,
                orig_amount=refunded_amount,
                orig_account=Transaction.REFUNDED,
                orig_organization=customer)

            if invoiced_fee:
                # Refund the processor fee (if exists)
                Transaction.objects.create(
                    event_id=self.id,
                    # The Charge id is already included in the description here.
                    descr=invoiced_fee.descr.replace(
                        'processor fee', 'refund processor fee'),
                    created_at=created_at,
                    dest_unit=processor_unit,
                    dest_amount=refunded_fee_amount,
                    dest_account=refund_type,
                    dest_organization=processor,
                    orig_unit=processor_unit,
                    orig_amount=refunded_fee_amount,
                    orig_account=Transaction.FUNDS,
                    orig_organization=processor)
                processor.funds_balance -= refunded_fee_amount
                processor.save()

            # cancel payment to provider
            Transaction.objects.create(
                event_id=self.id,
                descr=descr,
                created_at=created_at,
                dest_unit=processor_unit,
                dest_amount=refunded_distribute_amount,
                dest_account=refund_type,
                dest_organization=processor,
                orig_unit=provider_unit,
                orig_amount=refunded_distribute_amount,
                orig_account=Transaction.FUNDS,
                orig_organization=provider)
            provider.funds_balance -= refunded_distribute_amount
            provider.save()


class CouponManager(models.Manager):

    def active(self, organization, code, at_time=None):
        at_time = datetime_or_now(at_time)
        return self.filter(
            Q(ends_at__isnull=True) | Q(ends_at__gt=at_time),
            code__iexact=code, # case incensitive search.
            organization=organization)


class Coupon(models.Model):
    """
    Coupons are used on invoiced to give a rebate to a customer.
    """
    #pylint: disable=super-on-old-class
    objects = CouponManager()

    created_at = models.DateTimeField(auto_now_add=True)
    code = models.SlugField()
    description = models.TextField(null=True, blank=True)
    percent = models.PositiveSmallIntegerField(default=0,
        validators=[MaxValueValidator(100)],
        help_text="Percentage discounted")
    # restrict use in scope
    organization = models.ForeignKey(Organization)
    plan = models.ForeignKey('saas.Plan', null=True, blank=True)
    # restrict use in time and count.
    ends_at = models.DateTimeField(null=True, blank=True)
    nb_attempts = models.IntegerField(null=True, blank=True,
        help_text="Number of times the coupon can be used")

    class Meta:
        unique_together = ('organization', 'code')

    def __unicode__(self):
        return '%s-%s' % (self.organization, self.code)

    @property
    def provider(self):
        return self.organization

    def is_valid(self, plan, at_time=None):
        """
        Returns ``True`` if the ``Coupon`` can sucessfuly be applied
        to purchase this plan.
        """
        at_time = datetime_or_now(at_time)
        valid_plan = (not self.plan or self.plan == plan)
        valid_time = (not self.ends_at or self.ends_at < at_time)
        valid_attempts = (self.nb_attempts is None or self.nb_attempts > 0)
        valid_organization = (self.organization == plan.organization)
        return (valid_plan or valid_time or valid_attempts
            or valid_organization)

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if not self.created_at:
            self.created_at = datetime_or_now()
        # Implementation Note:
        # We want ``ends_at`` on a newly created ``Coupon`` to defaults
        # to an expiration date, yet we want to force an update on the Coupon
        # to enable a "never" expiration date. We can't enable both semantics
        # through ``ends_at == None``, so the serializer ``perform_update``
        # explicitely set ends_at to 'never' (not a datetime instance).
        if self.ends_at:
            if str(self.ends_at) == 'never':
                self.ends_at = None
        else:
            self.ends_at = self.created_at + datetime.timedelta(days=30)
        super(Coupon, self).save(force_insert=force_insert,
             force_update=force_update, using=using,
             update_fields=update_fields)


class PlanManager(models.Manager):

    def as_buy_periods(self, descr):
        """
        Returns a triplet (plan, ends_at, nb_periods) from a string
        formatted with DESCRIBE_BUY_PERIODS.
        """
        plan = None
        nb_periods = 0
        ends_at = datetime.datetime()
        look = re.match(DESCRIBE_BUY_PERIODS % {
                'plan': r'(?P<plan>\S+)',
                'ends_at': r'(?P<ends_at>\d\d\d\d/\d\d/\d\d)',
                'humanized_periods': r'(?P<nb_periods>\d+).*'}, descr)
        if look:
            try:
                plan = self.get(slug=look.group('plan'))
            except Plan.DoesNotExist:
                plan = None
            ends_at = datetime.datetime.strptime(
                look.group('ends_at'), '%Y/%m/%d').replace(tzinfo=utc)
            nb_periods = int(look.group('nb_periods'))
        return (plan, ends_at, nb_periods)

    @staticmethod
    def provider(plans):
        """
        If all plans are from the same provider, return it otherwise
        return the site broker.
        """
        result = None
        for plan in plans:
            if not result:
                result = plan.organization
            elif result != plan.organization:
                result = get_broker()
                break
        if not result:
            result = get_broker()
        return result


class Plan(models.Model):
    """
    Recurring billing plan
    """
    objects = PlanManager()

    UNSPECIFIED = 0
    HOURLY = 1
    DAILY = 2
    WEEKLY = 3
    MONTHLY = 4
    YEARLY = 5

    INTERVAL_CHOICES = [
        (HOURLY, "HOURLY"),
        (DAILY, "DAILY"),
        (WEEKLY, "WEEKLY"),
        (MONTHLY, "MONTHLY"),
        (YEARLY, "YEARLY"),
        ]

    PRICE_ROUND_NONE = 0
    PRICE_ROUND_WHOLE = 1
    PRICE_ROUND_99 = 2

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=50, null=True)
    description = models.TextField()
    is_active = models.BooleanField(default=False)
    is_not_priced = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    discontinued_at = models.DateTimeField(null=True, blank=True)
    organization = models.ForeignKey(Organization, related_name='plans')
    unit = models.CharField(max_length=3, default='usd')
    setup_amount = models.PositiveIntegerField(default=0,
        help_text=_('One-time charge amount (in cents).'))
    period_amount = models.PositiveIntegerField(default=0,
        help_text=_('Recurring amount per period (in cents).'))
    transaction_fee = models.PositiveIntegerField(default=0,
        help_text=_('Fee per transaction (in per 10000).'))
    interval = models.PositiveSmallIntegerField(
        choices=INTERVAL_CHOICES, default=YEARLY)
    period_length = models.PositiveSmallIntegerField(default=1,
        help_text=_('Natural number of months/years/etc. before the plan ends'))
    unlock_event = models.CharField(max_length=128, null=True, blank=True,
        help_text=_('Payment required to access full service'))
    advance_discount = models.PositiveIntegerField(default=333,
        validators=[MaxValueValidator(10000)], # 100.00%
        help_text=_('incr discount for payment of multiple periods (in %%).'))
    # end game
    length = models.PositiveSmallIntegerField(null=True, blank=True,
        help_text=_('Number of intervals the plan before the plan ends.'))
    auto_renew = models.BooleanField(default=True)
    # Pb with next : maybe create an other model for it
    next_plan = models.ForeignKey("Plan", null=True)

    class Meta:
        unique_together = ('slug', 'organization')

    def __unicode__(self):
        return unicode(self.slug)

    @property
    def period_price(self):
        return Price(self.period_amount, self.unit)

    @property
    def setup_price(self):
        return Price(self.setup_amount, self.unit)

    @property
    def yearly_amount(self):
        if self.interval == Plan.HOURLY:
            amount, _ = self.advance_period_amount(365 * 24)
        elif self.interval == Plan.DAILY:
            amount, _ = self.advance_period_amount(365)
        elif self.interval == Plan.WEEKLY:
            amount, _ = self.advance_period_amount(52)
        elif self.interval == Plan.MONTHLY:
            amount, _ = self.advance_period_amount(12)
        elif self.interval == Plan.YEARLY:
            amount, _ = self.advance_period_amount(1)
        return amount

    def advance_period_amount(self, nb_periods, rounding=PRICE_ROUND_WHOLE):
        assert nb_periods > 0
        discount_percent = self.advance_discount * (nb_periods - 1)
        if discount_percent >= 9999:
            # Hardcode to a maximum of 99.99% discount
            discount_percent = 9999
            return -1, discount_percent / 100
        discount_amount = (self.period_amount * nb_periods
                * (10000 - discount_percent) / 10000)
        if rounding == self.PRICE_ROUND_WHOLE:
            discount_amount += 100 - discount_amount % 100
        elif rounding == self.PRICE_ROUND_99:
            discount_amount += 99 - discount_amount % 100
        return discount_amount, discount_percent / 100

    def first_periods_amount(self, discount_percent=0, nb_natural_periods=1,
                              prorated_amount=0):
        amount = int((prorated_amount
            + (self.period_amount * nb_natural_periods))
            * (100 - discount_percent) / 100)
        return amount

    @staticmethod
    def get_natural_period(nb_periods, interval):
        result = None
        if interval == Plan.HOURLY:
            result = relativedelta(hours=1 * nb_periods)
        elif interval == Plan.DAILY:
            result = relativedelta(days=1 * nb_periods)
        elif interval == Plan.WEEKLY:
            result = relativedelta(days=7 * nb_periods)
        elif interval == Plan.MONTHLY:
            result = relativedelta(months=1 * nb_periods)
        elif interval == Plan.YEARLY:
            result = relativedelta(years=1 * nb_periods)
        return result

    def natural_period(self, nb_periods=1):
        return self.get_natural_period(nb_periods, self.interval)

    def end_of_period(self, start_time, nb_periods=1):
        result = start_time
        if nb_periods:
            # In case of a ``SETTLED``, *nb_periods* will be ``None``
            # since the description does not (should not) allow us to
            # extend the subscription length.
            natural = self.natural_period(nb_periods)
            if natural:
                result += natural
        return result

    def start_of_period(self, end_time, nb_periods=1):
        return self.end_of_period(end_time, nb_periods=-nb_periods)

    def get_title(self):
        """
        Returns a printable human-readable title for the plan.
        """
        if self.title:
            return self.title
        return self.slug

    def humanize_period(self, nb_periods):
        result = None
        if self.interval == self.HOURLY:
            result = '%d hour' % nb_periods
        elif self.interval == self.DAILY:
            result = '%d day' % nb_periods
        elif self.interval == self.WEEKLY:
            result = '%d week' % nb_periods
        elif self.interval == self.MONTHLY:
            result = '%d month' % nb_periods
        elif self.interval == self.YEARLY:
            result = '%d year' % nb_periods
        if result and nb_periods > 1:
            result += 's'
        return result

    def period_number(self, text):
        """
        This method is the reverse of ``humanize_period``. It will extract
        a number of periods from a text.
        """
        result = None
        if self.interval == self.HOURLY:
            pat = r'(\d+)(\s|-)hour'
        elif self.interval == self.DAILY:
            pat = r'(\d+)(\s|-)day'
        elif self.interval == self.WEEKLY:
            pat = r'(\d+)(\s|-)week'
        elif self.interval == self.MONTHLY:
            pat = r'(\d+)(\s|-)month'
        elif self.interval == self.YEARLY:
            pat = r'(\d+)(\s|-)year'
        else:
            raise ValueError("period type %d is not defined."
                % self.interval)
        look = re.search(pat, text)
        if look:
            try:
                result = int(look.group(1))
            except ValueError:
                pass
        return result

    def prorate_transaction(self, amount):
        """
        Hosting service paid through a transaction fee.
        """
        return (amount * self.transaction_fee) / 10000

    def prorate_period(self, start_time, end_time):
        """
        Return the pro-rate recurring amount for a period
        [start_time, end_time[.

        If end_time - start_time >= interval period, the value
        returned is undefined.
        """
        if self.interval == self.HOURLY:
            # Hourly: fractional period is in minutes.
            fraction = (end_time - start_time).seconds / 3600
        elif self.interval == self.DAILY:
            # Daily: fractional period is in hours.
            fraction = ((end_time - start_time).seconds
                        / (3600 * 24))
        elif self.interval == self.WEEKLY:
            # Weekly, fractional period is in days.
            fraction = (end_time.date() - start_time.date()).days / 7
        elif self.interval == self.MONTHLY:
            # Monthly: fractional period is in days.
            # We divide by the maximum number of days in a month to
            # the advantage of a customer.
            fraction = (end_time.date() - start_time.date()).days / 31
        elif self.interval == self.YEARLY:
            # Yearly: fractional period is in days.
            # We divide by the maximum number of days in a year to
            # the advantage of a customer.
            fraction = (end_time.date() - start_time.date()).days / 366
        # Round down to the advantage of a customer.
        return int(self.period_amount * fraction)


class CartItemManager(models.Manager):

    def get_cart(self, user, *args, **kwargs):
        # Order by plan then id so the order is consistent between
        # billing/cart(-.*)/ pages.
        return self.filter(user=user, recorded=False,
            *args, **kwargs).order_by('plan', 'id')

    def by_claim_code(self, claim_code, *args, **kwargs):
        # Order by plan then id so the order is consistent between
        # billing/cart(-.*)/ pages.
        return self.filter(claim_code=claim_code, recorded=False,
            user__isnull=True, *args, **kwargs).order_by('plan', 'id')

    @staticmethod
    def provider(cart_items):
        return Plan.objects.provider(
            [cart_item.plan for cart_item in cart_items])

    def redeem(self, user, coupon_code, created_at=None):
        """
        Apply a *coupon* to all items in a cart that accept it.
        """
        at_time = datetime_or_now(created_at)
        coupon_applied = False
        for item in self.get_cart(user):
            coupon = Coupon.objects.active(item.plan.organization, coupon_code,
                at_time=at_time).first()
            if coupon and coupon.is_valid(item.plan, at_time=at_time):
                coupon_applied = True
                item.coupon = coupon
                item.save()
        return coupon_applied


class CartItem(models.Model):
    """
    A user (authenticated or anonymous) shops for plans by adding them
    to her cart. When placing an order, the user is presented with the billing
    account (``Organization``) those items apply to.

    Historical Note: The billing account was previously required at the time
    the item is added to the cart. The ``cart_items`` is the only extra state
    kept in the session, and kept solely for anonymous users. We do not store
    the billing account in the session. It is retrieved from the url. As a
    result the billing account (i.e. an ``Organization``) is set when an
    order is placed, not when the item is added to the cart.

    Another Historical Note: If we allow a user to buy more periods at
    a bargain price, then ('user', 'plan', 'email') should not be unique
    together. There should only be one ``CartItem`` not yet recorded
    with ('user', 'plan', 'email') unique together.
    """
    objects = CartItemManager()

    created_at = models.DateTimeField(auto_now_add=True,
        help_text=_("date/time at which the item was added to the cart."))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='user_id',
        null=True, related_name='cart_items',
        help_text=_("user who added the item to the cart. ``None`` means"\
" the item could be claimed."))
    plan = models.ForeignKey(Plan, null=True,
        help_text=_("item added to the cart."))
    coupon = models.ForeignKey(Coupon, null=True,
        help_text=_("coupon to apply to the plan."))
    recorded = models.BooleanField(default=False,
        help_text=_("whever the item has been checked out or not."))

    # The following fields are for number of periods pre-paid in advance.
    nb_periods = models.PositiveIntegerField(default=0)

    # The following fields are used for plans priced per seat. They do not
    # refer to a User nor Organization key because those might not yet exist
    # at the time the seat is created.
    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    last_name = models.CharField(_('last name'), max_length=30, blank=True)
    email = models.EmailField(_('email address'), blank=True)

    # Items paid by user on behalf of a subscriber, that might or might not
    # already exist in the database, can be redeemed through a claim_code.
    claim_code = models.SlugField(null=True, blank=True)

    def __unicode__(self):
        return '%s-%s' % (self.user, self.plan)

    @property
    def descr(self):
        result = '%s from %s' % (
            self.plan.get_title(), self.plan.organization.printable_name)
        if self.email:
            full_name = ' '.join([self.first_name, self.last_name]).strip()
            result = 'Subscribe %s (%s) to %s' % (full_name, self.email, result)
        return result

    @property
    def name(self):
        result = 'cart-%s' % self.plan.slug
        if self.email:
            result = '%s-%s' % (result, quote(self.email))
        return result


class SubscriptionManager(models.Manager):
    #pylint: disable=super-on-old-class

    def active_for(self, organization, ends_at=None):
        """
        Returns active subscriptions for *organization*
        """
        ends_at = datetime_or_now(ends_at)
        return self.filter(organization=organization, ends_at__gt=ends_at)

    def active_with_provider(self, organization, provider, ends_at=None):
        """
        Returns a list of active subscriptions for organization
        for which provider is the owner of the plan.
        """
        ends_at = datetime_or_now(ends_at)
        return self.filter(organization=organization,
            plan__organization=provider, ends_at__gt=ends_at)

    def create(self, **kwargs):
        if not kwargs.has_key('ends_at'):
            created_at = datetime_or_now(kwargs.get('created_at', None))
            plan = kwargs.get('plan')
            return super(SubscriptionManager, self).create(
                ends_at=plan.end_of_period(created_at), **kwargs)
        return super(SubscriptionManager, self).create(**kwargs)

    def new_instance(self, organization, plan, ends_at=None):
        #pylint: disable=no-self-use
        """
        New ``Subscription`` instance which is explicitely not in the db.
        """
        return Subscription(organization=organization, plan=plan,
            auto_renew=plan.auto_renew, ends_at=ends_at)


class Subscription(models.Model):
    """
    ``Subscription`` represent a service contract (``Plan``) between
    two ``Organization``, a subscriber and a provider, that is paid
    by the subscriber to the provider over the lifetime of the subscription.

    When ``auto_renew`` is True, ``extend_subscriptions`` (usually called
    from a cron job) will invoice the organization for an additional period
    once the date reaches currenct end of subscription.

    Implementation Note:
    Even through (organization, plan) should be unique at any point in time,
    it is a little much to implement with PostgreSQL that for each
    (organization, plan), there should not be overlapping timeframe
    [created_at, ends_at[.
    """
    SEP = ':' # The separator must be a character which cannot be used in slugs.

    objects = SubscriptionManager()

    auto_renew = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ends_at = models.DateTimeField()
    description = models.TextField(null=True, blank=True)
    organization = models.ForeignKey(Organization)
    plan = models.ForeignKey(Plan)

    def __unicode__(self):
        return '%s%s%s' % (unicode(self.organization), Subscription.SEP,
            unicode(self.plan))

    @property
    def is_locked(self):
        balance, _ = \
            Transaction.objects.get_subscription_statement_balance(self)
        return balance > 0

    @property
    def provider(self):
        return self.plan.organization

    def period_for(self, at_time=None):
        """
        Returns the period [beg,end[ which includes ``at_time``.
        """
        at_time = datetime_or_now(at_time)
        delta = at_time - self.created_at
        if self.plan.interval == Plan.HOURLY:
            estimated = relativedelta(hours=delta.total_seconds() / 3600)
            period = relativedelta(hours=1)
        elif self.plan.interval == Plan.DAILY:
            estimated = relativedelta(days=delta.days)
            period = relativedelta(days=1)
        elif self.plan.interval == Plan.WEEKLY:
            estimated = relativedelta(days=delta.days / 7)
            period = relativedelta(days=7)
        elif self.plan.interval == Plan.MONTHLY:
            estimated = relativedelta(months=delta.days / 30)
            period = relativedelta(months=1)
        elif self.plan.interval == Plan.YEARLY:
            estimated = relativedelta(years=delta.days / 365)
            period = relativedelta(years=1)
        else:
            raise ValueError("period type %d is not defined."
                % self.plan.interval)
        lower = self.created_at + estimated # rough estimate to start
        upper = lower + period
        while not (lower <= at_time and at_time < upper):
            if at_time < lower:
                upper = lower
                lower = lower - period
            elif at_time >= upper:
                lower = upper
                upper = upper + period
        # Both lower and upper fall on an exact period multiple
        # from ``created_at``. This might not be the case for ``ends_at``.
        return (min(lower, self.ends_at), min(upper, self.ends_at))


    def nb_periods(self, start=None, until=None):
        """
        Returns the number of completed periods at datetime ``until``
        since the subscription was created.
        """
        if start is None:
            start = self.created_at
        until = datetime_or_now(until)
        assert start < until
        start_lower, start_upper = self.period_for(start)
        until_lower, until_upper = self.period_for(until)
        if start_upper < until_lower:
            delta = until_lower - start_upper
            if self.plan.interval == Plan.HOURLY:
                estimated = delta.total_seconds() / 3600
            elif self.plan.interval == Plan.DAILY:
                estimated = delta.days
            elif self.plan.interval == Plan.WEEKLY:
                estimated = delta.days / 7
            elif self.plan.interval == Plan.MONTHLY:
                estimated = relativedelta(until_lower, start_upper).months
            elif self.plan.interval == Plan.YEARLY:
                estimated = delta.days / 365
            upper = self.plan.end_of_period(start_upper, nb_periods=estimated)
#            LOGGER.debug("end of %d %s periods from %s => %s",
#               estimated, self.plan.get_interval_display(), start_upper, upper)
            if upper < until_lower:
                full_periods = estimated + 1
            else:
                full_periods = estimated
        else:
            full_periods = 0
        # partial-at-start + full periods + partial-at-end
        start_period_total_seconds = (start_upper - start_lower).total_seconds()
        if start_period_total_seconds > 0:
            partial_start_period = ((start_upper - start).total_seconds()
                / start_period_total_seconds)
        else:
            partial_start_period = 0
        end_period_total_seconds = (until_upper - until_lower).total_seconds()
        if end_period_total_seconds > 0:
            partial_end_period = ((until - until_lower).total_seconds()
                / end_period_total_seconds)
        else:
            partial_end_period = 0
        return partial_start_period + full_periods + partial_end_period

    def charge_in_progress(self):
        queryset = Charge.objects.filter(
            customer=self.organization, state=Charge.CREATED)
        if queryset.exists():
            return queryset.first()
        return None

    def unsubscribe_now(self):
        self.ends_at = datetime_or_now()
        self.auto_renew = False
        self.save()


class TransactionManager(models.Manager):

    def by_charge(self, charge):
        """
        Returns all transactions associated to a charge.
        """
        # XXX This might return ``Subscription`` but it is OK because
        # we later filter for movement on specific accounts
        # a ``Subscription`` cannot create.
        #
        # Implementation Note:
        # We have to explicitely cast item.pk here otherwise PostgreSQL
        # is not happy.
        return self.filter(Q(event_id=charge) | Q(
            event_id__in=[str(item.pk) for item in charge.charge_items.all()]))

    def by_customer(self, organization):
        """
        Return transactions related to this organization, as a customer.
        """
        # If we include ``dest_account=Transaction.LIABILITY``, the entries
        # used to balance the ledger will also appear. We exclude all
        # entries with ``orig_account=Transaction.PAYABLE`` to compensate.
        return self.filter(
            (Q(dest_organization=organization)
             & (Q(dest_account=Transaction.PAYABLE)
                |Q(dest_account=Transaction.LIABILITY)))
            |(Q(orig_organization=organization)
              & (Q(orig_account=Transaction.LIABILITY)
                 | Q(orig_account=Transaction.REFUNDED)))).exclude(
                     orig_account=Transaction.PAYABLE)

    def by_organization(self, organization, account=None):
        """
        Returns all ``Transaction`` going in or out of an *account*
        for an *organization*.
        """
        if not account:
            account = Transaction.FUNDS
        return self.filter(
            # All transactions involving Funds
            ((Q(orig_organization=organization)
              & Q(orig_account=account))
            | (Q(dest_organization=organization)
              & Q(dest_account=account))))

    def by_subsciptions(self, subscriptions, at_time=None):
        """
        Returns a ``QuerySet`` of all transactions related to a set
        of subscriptions.
        """
        queryset = self.filter(
            dest_account=Transaction.PAYABLE,
            event_id__in=subscriptions)
        if at_time:
            queryset = queryset.filter(created_at=at_time)
        return queryset.order_by('created_at')

    def offline_payment(self, subscription, amount,
                        descr=None, user=None, created_at=None):
        #pylint: disable=too-many-arguments
        """
        For an offline payment, we will record a sequence of ``Transaction``
        as if we went through a ``new_subscription_order`` followed by
        ``payment_successful`` and ``withdraw_funds`` while bypassing
        the processor.

        Thus an offline payment is recorded as follow::

            ; Record an order

            yyyy/mm/dd description
                subscriber:Payable                       amount
                provider:Receivable

            ; Record the off-line payment

            yyyy/mm/dd charge event
                provider:Funds                           amount
                subscriber:Liability

            ; Compensate for atomicity of charge record (when necessary)

            yyyy/mm/dd invoiced-item event
                subscriber:Liability           min(invoiced_item_amount,
                subscriber:Payable                      balance_payable)

            ; Distribute funds to the provider

            yyyy/mm/dd distribution to provider (backlog accounting)
                provider:Receivable                      amount
                provider:Backlog

            yyyy/mm/dd mark the amount as offline payment
                provider:Offline                         amount
                provider:Funds

        Example::

            2014/09/10 subscribe to open-space plan
                xia:Payable                             $179.99
                cowork:Receivable

            2014/09/10 Check received off-line
                cowork:Funds                            $179.99
                xia:Liability

            2014/09/10 Keep a balanced ledger
                xia:Liability                           $179.99
                xia:Payable

            2014/09/10 backlog accounting
                cowork:Receivable                       $179.99
                cowork:Backlog

            2014/09/10 mark payment as processed off-line
                cowork:Offline                          $179.99
                cowork:Funds
        """
        if descr is None:
            descr = DESCRIBE_OFFLINE_PAYMENT
        if user:
            descr += ' (%s)' % user.username
        created_at = datetime_or_now(created_at)
        with transaction.atomic():
            self.create(
                created_at=created_at,
                descr=descr,
                event_id=subscription.id,
                dest_amount=amount,
                dest_unit=subscription.plan.unit,
                dest_account=Transaction.PAYABLE,
                dest_organization=subscription.organization,
                orig_amount=amount,
                orig_unit=subscription.plan.unit,
                orig_account=Transaction.RECEIVABLE,
                orig_organization=subscription.plan.organization)

            self.create(
                created_at=created_at,
                descr=descr,
                dest_amount=amount,
                dest_unit=subscription.plan.unit,
                dest_account=Transaction.FUNDS,
                dest_organization=subscription.plan.organization,
                orig_amount=amount,
                orig_unit=subscription.plan.unit,
                orig_account=Transaction.LIABILITY,
                orig_organization=subscription.organization)

            # If there is still an amount on the ``Payable`` account,
            # we create Payable to Liability transaction in order to correct
            # the accounts amounts. This is a side effect of the atomicity
            # requirement for a ``Transaction`` associated to offline payment.
            balance = self.get_event_balance(subscription.id,
                account=Transaction.PAYABLE)
            balance_payable = balance['amount']
            if balance_payable > 0:
                available = min(amount, balance_payable)
                Transaction.objects.create(
                    event_id=subscription.id,
                    created_at=created_at,
                    descr=DESCRIBE_DOUBLE_ENTRY_MATCH,
                    dest_amount=available,
                    dest_unit=subscription.plan.unit,
                    dest_account=Transaction.LIABILITY,
                    dest_organization=subscription.organization,
                    orig_amount=available,
                    orig_unit=subscription.plan.unit,
                    orig_account=Transaction.PAYABLE,
                    orig_organization=subscription.organization)

            self.create(
                created_at=created_at,
                descr=descr,
                event_id=subscription.id,
                dest_amount=amount,
                dest_unit=subscription.plan.unit,
                dest_account=Transaction.RECEIVABLE,
                dest_organization=subscription.plan.organization,
                orig_amount=amount,
                orig_unit=subscription.plan.unit,
                orig_account=Transaction.BACKLOG,
                orig_organization=subscription.plan.organization)

            self.create(
                created_at=created_at,
                descr="%s - %s" % (descr, DESCRIBE_DOUBLE_ENTRY_MATCH),
                event_id=subscription.id,
                dest_amount=amount,
                dest_unit=subscription.plan.unit,
                dest_account=Transaction.OFFLINE,
                dest_organization=subscription.plan.organization,
                orig_amount=amount,
                orig_unit=subscription.plan.unit,
                orig_account=Transaction.FUNDS,
                orig_organization=subscription.plan.organization)


    def distinct_accounts(self):
        return (set([val['orig_account']
                    for val in self.all().values('orig_account').distinct()])
                | set([val['dest_account']
                    for val in self.all().values('dest_account').distinct()]))

    def execute_order(self, invoiced_items, user=None):
        """
        Save invoiced_items, a set of ``Transaction`` and update when
        each associated ``Subscription`` ends.

        This method returns the invoiced items as a QuerySet.

        Constraints: All invoiced_items to same customer
        """
        invoiced_items_ids = []
        for invoiced_item in invoiced_items:
            # When an customer pays on behalf of an organization
            # which does not exist in the database, we cannot create
            # a ``Subscription`` since we don't have an ``Organization`` yet.
            pay_now = True
            subscription = invoiced_item.get_event()
            if subscription and isinstance(subscription, Subscription):
                subscription.ends_at = subscription.plan.end_of_period(
                    subscription.ends_at,
                    subscription.plan.period_number(invoiced_item.descr))
                subscription.save()
                if (subscription.plan.unlock_event
                    and invoiced_item.dest_amount == 0):
                    # We are dealing with access now, pay later, orders.
                    invoiced_item.dest_amount = subscription.plan.period_amount
                    pay_now = False
            if pay_now:
                invoiced_item.save()
                invoiced_items_ids += [invoiced_item.id]
        if len(invoiced_items_ids) > 0:
            signals.order_executed.send(
                sender=__name__, invoiced_items=invoiced_items_ids, user=user)
        return self.filter(id__in=invoiced_items_ids)

    def get_invoiceables(self, organization, until=None):
        """
        Returns a set of payable or liability ``Transaction`` since
        the last successful payment by an ``organization``.
        """
        until = datetime_or_now(until)
        last_payment = self.filter(
            Q(orig_account=Transaction.PAYABLE)
            | Q(orig_account=Transaction.LIABILITY),
            orig_organization=organization,
            dest_account=Transaction.FUNDS,
            created_at__lt=until).order_by('-created_at').first()
        if last_payment:
            # Use ``created_at`` strictly greater than last payment date
            # otherwise we pick up the last payment itself.
            kwargs = {'created_at__gt':last_payment.created_at}
        else:
            kwargs = {}
        return self.filter(
            Q(dest_account=Transaction.PAYABLE)
            | Q(dest_account=Transaction.LIABILITY),
            dest_organization=organization, **kwargs)

    def get_capture(self, order):
        """
        Returns ``Transaction`` that corresponds to the capture
        of the Receivable generated by *order*.
        """
        return self.filter(event_id=order.event_id,
            orig_account=Transaction.BACKLOG,
            dest_account=Transaction.RECEIVABLE,
            created_at__gte=order.created_at).order_by('created_at').first()

    def get_balance(self, organization=None, account=None, like_account=None,
                    starts_at=None, ends_at=None, **kwargs):
        """
        Returns the balance ``until`` a certain date (Today by default).
        The balance can be constraint to a single organization and/or
        for a specific account. The account can be fully qualified or
        a selector pattern.
        """
        #pylint:disable=too-many-locals,too-many-arguments
        dest_params = {}
        orig_params = {}
        dest_params.update(kwargs)
        orig_params.update(kwargs)
        if starts_at:
            dest_params.update({'created_at__gte': starts_at})
            orig_params.update({'created_at__gte': starts_at})
        if ends_at:
            dest_params.update({'created_at__lt': ends_at})
            orig_params.update({'created_at__lt': ends_at})
        if organization is not None:
            dest_params.update({'dest_organization': organization})
            orig_params.update({'orig_organization': organization})
        if account is not None:
            dest_params.update({'dest_account': account})
            orig_params.update({'orig_account': account})
        elif like_account is not None:
            dest_params.update({'dest_account__icontains': like_account})
            orig_params.update({'orig_account__icontains': like_account})
        balance = sum_dest_amount(self.filter(**dest_params))
        dest_amount = balance['amount']
        dest_unit = balance['unit']
        dest_created_at = balance['created_at']
        balance = sum_orig_amount(self.filter(**orig_params))
        orig_amount = balance['amount']
        orig_unit = balance['unit']
        orig_created_at = balance['created_at']
        if dest_unit is None:
            unit = orig_unit
        elif orig_unit is None:
            unit = dest_unit
        elif dest_unit != orig_unit:
            raise ValueError('orig and dest balances until %s for account'\
' %s of %s have different unit (%s vs. %s).' % (datetime_or_now(ends_at),
                account, organization, orig_unit, dest_unit))
        else:
            unit = dest_unit
        return {'amount': dest_amount - orig_amount, 'unit': unit,
            'created_at': max(dest_created_at, orig_created_at)}

    def get_statement_balance(self, organization, until=None):
        until = datetime_or_now(until)
        balance = sum_dest_amount(self.filter(
            Q(dest_account=Transaction.PAYABLE)
            | Q(dest_account=Transaction.LIABILITY),
            dest_organization=organization,
            created_at__lt=until))
        dest_amount = balance['amount']
        dest_unit = balance['unit']
        balance = sum_orig_amount(self.filter(
            Q(orig_account=Transaction.PAYABLE)
            | Q(orig_account=Transaction.LIABILITY),
            orig_organization=organization,
            created_at__lt=until))
        orig_amount = balance['amount']
        orig_unit = balance['unit']
        if dest_unit is None:
            unit = orig_unit
        elif orig_unit is None:
            unit = dest_unit
        elif dest_unit != orig_unit:
            raise ValueError('orig and dest balances until %s for statement'\
' of %s have different unit (%s vs. %s).' % (until, organization,
                orig_unit, dest_unit))
        else:
            unit = dest_unit
        return dest_amount - orig_amount, unit

    def get_subscription_statement_balance(self, subscription):
        # XXX A little long but no better so far.
        #pylint:disable=invalid-name
        """
        Returns the balance of ``Payable`` and ``Liability`` treated
        as a single account for a subscription.

        The balance on a subscription is used to determine when
        a subscription is locked (balance due) or unlocked (no balance).
        """
        # Implementation Note:
        # The ``event_id`` associated to the unique ``Transaction` recording
        # a ``Charge`` will be the ``Charge.id``. As a result, getting the
        # amount due on a subscription by itself is more complicated than
        # just filtering by account and event_id.
        balance = sum_dest_amount(
            self.get_invoiceables(subscription.organization).filter(
                event_id=subscription.id))
        dest_amount = balance['amount']
        dest_unit = balance['unit']
        return dest_amount, dest_unit

    def get_event_balance(self, event_id,
                          account=None, starts_at=None, ends_at=None):
        """
        Returns the balance on a *event_id* for an *account*
        for the period [*starts_at*, *ends_at*[ as a tuple (amount, unit).
        """
        return self.get_balance(event_id=event_id, account=account,
            starts_at=starts_at, ends_at=ends_at)

    def get_subscription_income_balance(self, subscription,
                                        starts_at=None, ends_at=None):
        """
        Returns the recognized income balance on a subscription
        for the period [starts_at, ends_at[ as a tuple (amount, unit).
        """
        return self.get_event_balance(subscription.id,
            account=Transaction.INCOME, starts_at=starts_at, ends_at=ends_at)

    def get_subscription_invoiceables(self, subscription, until=None):
        """
        Returns a set of payable or liability ``Transaction`` since
        the last successful payment on a subscription.
        """
        until = datetime_or_now(until)
        last_payment = self.filter(
            Q(orig_account=Transaction.PAYABLE)
            | Q(orig_account=Transaction.LIABILITY),
            event_id=subscription.id,
            orig_organization=subscription.organization,
            dest_account=Transaction.FUNDS,
            created_at__lt=until).order_by('created_at').first()
        if last_payment:
            # Use ``created_at`` strictly greater than last payment date
            # otherwise we pick up the last payment itself.
            kwargs = {'created_at__gt':last_payment.created_at}
        else:
            kwargs = {}
        return self.filter(
            Q(dest_account=Transaction.PAYABLE)
            | Q(dest_account=Transaction.LIABILITY),
            event_id=subscription.id,
            dest_organization=subscription.organization, **kwargs)

    def get_subscription_receivable(self, subscription,
                                    starts_at=None, until=None):
        """
        Returns the receivable transactions on a subscription
        in the period [starts_at, ends_at[.
        """
        kwargs = {}
        if starts_at:
            kwargs.update({'created_at__gte': starts_at})
        until = datetime_or_now(until)
        return self.filter(
            orig_account=Transaction.RECEIVABLE,
            event_id=subscription.id,
            created_at__lt=until, **kwargs).order_by('created_at')

    @staticmethod
    def new_subscription_order(subscription, nb_natural_periods,
        prorated_amount=0, created_at=None, descr=None, discount_percent=0,
        descr_suffix=None):
        #pylint: disable=too-many-arguments
        """
        Each time a subscriber places an order through
        the /billing/:organization/cart/ page, a ``Transaction``
        is recorded as follow::

            yyyy/mm/dd description
                subscriber:Payable                       amount
                provider:Receivable

        Example::

            2014/09/10 subscribe to open-space plan
                xia:Payable                             $179.99
                cowork:Receivable

        At first, ``nb_periods``, the number of period paid in advance,
        is stored in the ``Transaction.orig_amount``. The ``Transaction``
        is created in ``TransactionManager.new_subscription_order``, then only
        later saved when ``TransactionManager.execute_order`` is called through
        ``Organization.checkout``. ``execute_order`` will replace
        ``orig_amount`` by the correct amount in the expected currency.
        """
        nb_periods = nb_natural_periods * subscription.plan.period_length
        if not descr:
            amount = subscription.plan.first_periods_amount(
                discount_percent=discount_percent,
                nb_natural_periods=nb_natural_periods,
                prorated_amount=prorated_amount)
            ends_at = subscription.plan.end_of_period(
                subscription.ends_at, nb_periods)
            # descr will later be use to recover the ``period_number``,
            # so we need to use The true ``nb_periods`` and not the number
            # of natural periods.
            descr = describe_buy_periods(
                subscription.plan, ends_at, nb_periods,
                discount_percent=discount_percent, descr_suffix=descr_suffix)
        else:
            # If we already have a description, all bets are off on
            # what the amount represents (see unlock_event).
            amount = prorated_amount
        created_at = datetime_or_now(created_at)
        return Transaction(
            created_at=created_at,
            descr=descr,
            event_id=subscription.id,
            dest_amount=amount,
            dest_unit=subscription.plan.unit,
            dest_account=Transaction.PAYABLE,
            dest_organization=subscription.organization,
            orig_amount=amount,
            orig_unit=subscription.plan.unit,
            orig_account=Transaction.RECEIVABLE,
            orig_organization=subscription.plan.organization)

    def new_subscription_later(self, subscription, created_at=None):
        """
        Returns a ``Transaction`` for the subscription balance
        to be paid later.
        """
        return self.new_subscription_statement(subscription,
            created_at=created_at, descr_pat=DESCRIBE_BALANCE + '- Pay later',
            balance_now=0)

    def new_subscription_statement(self, subscription, created_at=None,
                                   descr_pat=None, balance_now=None):
        """
        Since the ordering system is tightly coupled to the ``Transaction``
        ledger, we create special "none" transaction that are referenced
        when a ``Charge`` is created for payment of a balance due
        by a subcriber::

            yyyy/mm/dd description
                subscriber:Settled                        amount
                provider:Settled

        Example::

            2014/09/10 balance due
                xia:Settled                             $179.99
                cowork:Settled
        """
        created_at = datetime_or_now(created_at)
        balance, unit = self.get_subscription_statement_balance(subscription)
        if balance_now is None:
            balance_now = balance
        if descr_pat is None:
            descr_pat = DESCRIBE_BALANCE
        return Transaction(
            event_id=subscription.id,
            created_at=created_at,
            descr=descr_pat % {'amount': as_money(balance, unit),
                'plan': subscription.plan},
            dest_unit=unit,
            dest_amount=balance_now,
            dest_account=Transaction.SETTLED,
            dest_organization=subscription.organization,
            orig_unit=unit,
            orig_amount=balance_now,
            orig_account=Transaction.SETTLED,
            orig_organization=subscription.plan.organization)

    def create_period_started(self, subscription, created_at=None):
        """
        When a period starts and we have a payable balance
        for a subscription, we transfer it to a ``Liability``
        account, recorded as follow::

            yyyy/mm/dd description
                subscriber:Liability                     period_amount
                subscriber:Payable

        Example::

            2014/09/10 past due for period 2014/09/10 to 2014/10/10
                xia:Liability                             $179.99
                xia:Payable
        """
        created_at = datetime_or_now(created_at)
        amount = subscription.plan.period_amount
        return self.create(
            created_at=created_at,
            descr=DESCRIBE_LIABILITY_START_PERIOD,
            dest_amount=amount,
            dest_unit=subscription.plan.unit,
            dest_account=Transaction.LIABILITY,
            dest_organization=subscription.organization,
            orig_amount=amount,
            orig_unit=subscription.plan.unit,
            orig_account=Transaction.PAYABLE,
            orig_organization=subscription.organization,
            event_id=subscription.id)

    def create_income_recognized(self, subscription,
        amount=0, starts_at=None, ends_at=None, descr=None, dry_run=False):
        """
        When a period ends and we either have a ``Backlog`` (payment
        was made before the period starts) or a ``Receivable`` (invoice
        is submitted after the period ends). Either way we must recognize
        income for that period since the subscription was serviced::

            yyyy/mm/dd When payment was made at begining of period
                provider:Backlog                   period_amount
                provider:Income

            yyyy/mm/dd When service is invoiced after period ends
                provider:Backlog                   period_amount
                provider:Income

        Example::

            2014/09/10 recognized income for period 2014/09/10 to 2014/10/10
                cowork:Backlog                         $179.99
                cowork:Income
        """
        #pylint:disable=unused-argument,too-many-arguments
        created_transactions = []
        ends_at = datetime_or_now(ends_at)
        # ``created_at`` is set just before ``ends_at``
        # so we do not include the newly created transaction
        # in the subsequent period.
        created_at = ends_at - relativedelta(seconds=1)
        balance = self.get_event_balance(subscription.id,
            account=Transaction.BACKLOG, ends_at=ends_at)
        backlog_amount = - balance['amount'] # def. balance must be negative
        balance = self.get_event_balance(subscription.id,
            account=Transaction.RECEIVABLE, ends_at=ends_at)
        receivable_amount = - balance['amount'] # def. balance must be negative
        LOGGER.debug("recognize %dc with %dc backlog available,"\
            " %dc receivable available at %s",
            amount, backlog_amount, receivable_amount, ends_at)
        assert backlog_amount >= 0 or receivable_amount >= 0
        if amount > 0 and backlog_amount > 0:
            available = min(amount, backlog_amount)
            LOGGER.info(
                'RECOGNIZE BACKLOG %dc for %s at %s',
                available, subscription, created_at)
            recognized = Transaction(
                created_at=created_at,
                descr=descr,
                event_id=subscription.id,
                dest_amount=available,
                dest_unit=subscription.plan.unit,
                dest_account=Transaction.BACKLOG,
                dest_organization=subscription.plan.organization,
                orig_amount=available,
                orig_unit=subscription.plan.unit,
                orig_account=Transaction.INCOME,
                orig_organization=subscription.plan.organization)
            if not dry_run:
                recognized.save()
            created_transactions += [recognized]
            amount -= available
        if amount > 0 and receivable_amount > 0:
            available = min(amount, receivable_amount)
            LOGGER.info(
                'RECOGNIZE RECEIVABLE %dc for %s at %s',
                available, subscription, created_at)
            recognized = Transaction(
                created_at=created_at,
                descr=descr,
                event_id=subscription.id,
                dest_amount=available,
                dest_unit=subscription.plan.unit,
                dest_account=Transaction.RECEIVABLE,
                dest_organization=subscription.plan.organization,
                orig_amount=available,
                orig_unit=subscription.plan.unit,
                orig_account=Transaction.INCOME,
                orig_organization=subscription.plan.organization)
            if not dry_run:
                recognized.save()
            created_transactions += [recognized]
            amount -= available
        assert amount == 0
        return created_transactions

    @staticmethod
    def providers(invoiced_items):
        """
        If all subscriptions referenced by *invoiced_items* are to the same
        provider, return it otherwise return the site owner.
        """
        results = set([])
        for invoiced_item in invoiced_items:
            event = invoiced_item.get_event()
            if event:
                results |= set([event.provider])
        return list(results)

    @staticmethod
    def by_processor_key(invoiced_items):
        """
        Returns a dictionnary {processor_key: [invoiced_item ...]}
        such that all invoiced_items appear under a processor_key.
        """
        results = {}
        default_processor_key = get_broker().processor_backend.pub_key
        for invoiced_item in invoiced_items:
            event = invoiced_item.get_event()
            if event:
                processor_key = event.provider.processor_backend.pub_key
                if not processor_key:
                    processor_key = default_processor_key
            else:
                processor_key = default_processor_key
            if not processor_key in results:
                results[processor_key] = []
            results[processor_key] += [invoiced_item]
        return results


class Transaction(models.Model):
    """
    The Transaction table stores entries in the double-entry bookkeeping
    ledger.

    'Invoiced' comes from the service. We use for acrual tax reporting.
    We have one 'invoiced' for each job? => easy to reconciliate.

    'Balance' is amount due.

    use 'ledger register' for tax acrual tax reporting.
    """
    # provider side
    FUNDS = 'Funds'           # "Cash" account.
    WITHDRAW = 'Withdraw'     # >= 0
    REFUND = 'Refund'         # >= 0
    CHARGEBACK = 'Chargeback'
    WRITEOFF = 'Writeoff'      # unused
    RECEIVABLE = 'Receivable' # always <= 0
    BACKLOG = 'Backlog'       # always <= 0
    INCOME = 'Income'         # always <= 0
    OFFLINE = 'Offline'
    EXPENSES = 'Expenses'

    # subscriber side
    PAYABLE = 'Payable'       # always >= 0
    LIABILITY = 'Liability'   # always >= 0
    REFUNDED = 'Refunded'     # always <= 0

    # ``Transaction`` that can be referenced as an invoiced item
    # when we can attempt to charge a balance due.
    SETTLED = 'settled'


    objects = TransactionManager()

    # Implementation Note:
    # An exact created_at is to important to let auto_now_add mess with it.
    created_at = models.DateTimeField()

    orig_account = models.CharField(max_length=255, default="unknown")
    orig_organization = models.ForeignKey(Organization,
        related_name="outgoing")
    orig_amount = models.PositiveIntegerField(default=0,
        help_text=_('amount withdrawn from origin in origin units'))
    orig_unit = models.CharField(max_length=3, default="usd",
        help_text=_('Measure of units on origin account'))

    dest_account = models.CharField(max_length=255, default="unknown")
    dest_organization = models.ForeignKey(Organization,
        related_name="incoming")
    dest_amount = models.PositiveIntegerField(default=0,
        help_text=_('amount deposited into destination in destination units'))
    dest_unit = models.CharField(max_length=3, default="usd",
        help_text=_('Measure of units on destination account'))

    # Optional
    descr = models.TextField(default="N/A")
    event_id = models.SlugField(null=True, help_text=
        _('Event at the origin of this transaction (ex. job, charge, etc.)'))

    def __unicode__(self):
        return unicode(self.id)

    @property
    def dest_price(self):
        return Price(self.dest_amount, self.dest_unit)

    @property
    def orig_price(self):
        return Price(self.orig_amount, self.orig_unit)

    def is_debit(self, organization):
        '''
        Return True if this transaction is a debit (negative ledger entry).
        '''
        return ((self.orig_organization == organization       # customer
                 and self.dest_account == Transaction.FUNDS)
                or (self.orig_organization == organization    # provider
                 and self.orig_account == Transaction.FUNDS))

    def get_event(self):
        """
        Returns the associated 'event' (Subscription, Coupon, etc)
        if available.
        """
        if self.event_id:
            try:
                return Subscription.objects.get(id=self.event_id)
            except (Subscription.DoesNotExist, ValueError):
                pass
            try:
                return Coupon.objects.get(code=self.event_id)
            except (Coupon.DoesNotExist, ValueError):
                pass
        return None


class BalanceLine(models.Model):
    """
    Defines a line in a balance sheet. All ``Transaction`` account matching
    ``selector`` will be aggregated over a period of time.
    """
    report = models.SlugField()
    title = models.CharField(max_length=255)
    selector = models.CharField(max_length=255)
    rank = models.IntegerField()
    moved = models.BooleanField(default=False)

    class Meta:
        unique_together = ('report', 'rank', 'moved')

    def __unicode__(self):
        return '%s/%d' % (self.report, self.rank)


def get_broker():
    """
    Returns the site-wide provider from a request.
    """
    broker_slug = settings.PLATFORM
    if settings.BROKER_CALLABLE:
        from saas.compat import import_string
        broker_slug = str(import_string(settings.BROKER_CALLABLE)())
    LOGGER.debug("get_broker('%s')", broker_slug)
    return Organization.objects.get(slug=broker_slug)


def sum_dest_amount(transactions):
    """
    Return the sum of the amount in the *transactions* set.
    """
    query_result = []
    if isinstance(transactions, QuerySet):
        if transactions.exists():
            query_result = transactions.values('dest_unit').annotate(
                Sum('dest_amount'), Max('created_at')).distinct()
    else:
        group_by = {}
        most_recent = None
        for item in transactions:
            if not most_recent or item.created_at < most_recent:
                most_recent = item.created_at
            if not item.dest_unit in group_by:
                group_by[item.dest_unit] = 0
            group_by[item.dest_unit] += item.dest_amount
        for unit, amount in group_by.iteritems():
            query_result += [{'dest_unit': unit, 'dest_amount__sum': amount,
                'created_at__max': most_recent}]
    if len(query_result) > 0:
        if len(query_result) > 1:
            try:
                raise ValueError("sum accross %d units (%s)" %
                    (len(query_result), ','.join(
                        [res['dest_unit'] for res in query_result])))
            except ValueError as err:
                LOGGER.error(extract_full_exception_stack(err))
        # XXX Hack: until we change the function signature
        return {'amount': query_result[0]['dest_amount__sum'],
                'unit': query_result[0]['dest_unit'],
                'created_at': query_result[0]['created_at__max']}
    return {'amount': 0, 'unit': None, 'created_at': datetime_or_now()}


def sum_orig_amount(transactions):
    """
    Return the sum of the amount in the *transactions* set.
    """
    query_result = []
    if isinstance(transactions, QuerySet):
        if transactions.exists():
            query_result = transactions.values('orig_unit').annotate(
                Sum('orig_amount'), Max('created_at')).distinct()
    else:
        group_by = {}
        most_recent = None
        for item in transactions:
            if not most_recent or item.created_at < most_recent:
                most_recent = item.created_at
            if not item.orig_unit in group_by:
                group_by[item.orig_unit] = 0
            group_by[item.orig_unit] += item.orig_amount
        for unit, amount in group_by.iteritems():
            query_result += [{'orig_unit': unit, 'orig_amount__sum': amount,
                'created_at__max': most_recent}]
    if len(query_result) > 0:
        if len(query_result) > 1:
            try:
                raise ValueError("sum accross %d units (%s)" %
                    (len(query_result), ', '.join(
                        [res['orig_unit'] for res in query_result])))
            except ValueError as err:
                LOGGER.error(extract_full_exception_stack(err))
        # XXX Hack: until we change the function signature
        return {'amount': query_result[0]['orig_amount__sum'],
                'unit': query_result[0]['orig_unit'],
                'created_at': query_result[0]['created_at__max']}
    return {'amount': 0, 'unit': None, 'created_at': datetime_or_now()}
