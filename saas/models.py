#pylint: disable=too-many-lines

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

import datetime, logging, re

from dateutil.relativedelta import relativedelta
from django.core.validators import MaxValueValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Q, Sum
from django.db.models.query import QuerySet
from django.utils.http import quote
from django.utils.decorators import method_decorator
from django.utils.timezone import utc
from django.utils.translation import ugettext_lazy as _
from django_countries.fields import CountryField

from saas import settings
from saas import signals
from saas import get_manager_relation_model, get_contributor_relation_model
from saas.backends import get_processor_backend, ProcessorError, CardError
from saas.utils import datetime_or_now, generate_random_slug

from saas.humanize import (as_money, describe_buy_periods,
    DESCRIBE_BUY_PERIODS, DESCRIBE_BALANCE,
    DESCRIBE_CHARGED_CARD, DESCRIBE_CHARGED_CARD_PROCESSOR,
    DESCRIBE_CHARGED_CARD_PROVIDER, DESCRIBE_CHARGED_CARD_REFUND,
    DESCRIBE_DOUBLE_ENTRY_MATCH, DESCRIBE_LIABILITY_START_PERIOD)

LOGGER = logging.getLogger(__name__)

#pylint: disable=old-style-class,no-init


class InsufficientFunds(Exception):

    pass


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

    def accessible_by(self, user):
        """
        Returns a QuerySet of Organziation which *user* either has
        a manager or contributor relation to.

        When *user* is a string instead of a ``User`` instance, it will
        be interpreted as a username.
        """
        if isinstance(user, basestring):
            return self.filter(Q(managers__username=user)
                | Q(contributors__username=user))
        return self.filter(Q(managers__pk=user.pk)
                | Q(contributors__pk=user.pk))


    def find_contributed(self, user):
        """
        Returns a QuerySet of Organziation for which the user is a contributor.
        """
        return self.filter(contributors__id=user.id)

    def find_managed(self, user):
        """
        Returns a QuerySet of Organziation for which *user* is a manager.

        When *user* is a string instead of a ``User`` instance, it will
        be interpreted as a username.
        """
        if isinstance(user, str):
            return self.filter(managers__username=user)
        return self.filter(managers__pk=user.pk)

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


class Organization_Managers(models.Model): #pylint: disable=invalid-name

    organization = models.ForeignKey('Organization')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='user_id')

    class Meta:
        unique_together = ('organization', 'user')

    def __unicode__(self):
        return '%s-%s' % (unicode(self.organization), unicode(self.user))


class Organization_Contributors(models.Model): #pylint: disable=invalid-name

    organization = models.ForeignKey('Organization')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='user_id')

    class Meta:
        unique_together = ('organization', 'user')

    def __unicode__(self):
        return '%s-%s' % (unicode(self.organization), unicode(self.user))


class Organization(models.Model):
    """
    The Organization table stores information about who gets
    charged (and who gets paid) for using the service. Users can
    have one of two relationships with an Organization. They can
    either be managers (all permissions) or contributors (use permissions).
    """

    objects = OrganizationManager()
    slug = models.SlugField(unique=True,
        help_text=_("Name of the organization as shown in the url bar."))

    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_bulk_buyer = models.BooleanField(default=False,
        help_text=_("Enable this organization to pay subscriptions on behalf"\
" of others."))
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

    managers = models.ManyToManyField(settings.AUTH_USER_MODEL,
        related_name='manages', through=settings.MANAGER_RELATION)

    contributors = models.ManyToManyField(settings.AUTH_USER_MODEL,
        related_name='contributes', through=settings.CONTRIBUTOR_RELATION)

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
    processor_recipient_id = models.CharField(
        null=True, blank=True, max_length=40,
        help_text=_("Used to deposit funds to the organization bank account"))

    def __unicode__(self):
        return unicode(self.slug)

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if not self.processor:
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
        return self.processor_recipient_id

    @property
    def natural_interval(self):
        plan_periods = self.plans.values('interval').distinct()
        interval = Plan.MONTHLY
        if len(plan_periods) == 1:
            interval = plan_periods[0]['interval']
        return interval

    @property
    def processor_backend(self):
        if not hasattr(self, '_processor_backend'):
            self._processor_backend = get_processor_backend(self.processor)
        return self._processor_backend

    def _add_relation(self, user, model, role, reason=None):
        # Implementation Note:
        # Django get_or_create will call router.db_for_write without
        # an instance so the using database will be lost. The following
        # code saves the relation in the correct database associated
        # with the organization.
        queryset = model.objects.db_manager(using=self._state.db).filter(
            organization=self, user=user)
        if not queryset.exists():
            m2m = model(organization=self, user=user)
            m2m.save(using=self._state.db, force_insert=True)
            signals.user_relation_added.send(sender=__name__,
                organization=self, user=user, role=role, reason=reason)
            return True
        return False

    def add_contributor(self, user, at_time=None, reason=None):
        """
        Add user as a contributor to organization.
        """
        #pylint: disable=unused-argument
        return self._add_relation(user, get_contributor_relation_model(),
            'contributor', reason=reason)

    def add_manager(self, user, at_time=None, reason=None):
        """
        Add user as a manager to organization.
        """
        #pylint: disable=unused-argument
        return self._add_relation(user, get_manager_relation_model(),
            'manager', reason=reason)

    def update_bank(self, bank_token):
        self.processor_backend.create_or_update_bank(self, bank_token)
        LOGGER.info('Updated bank information for %s on processor '\
            '{"recipient_id": %s}', self, self.processor_recipient_id)
        signals.bank_updated.send(self)

    def update_card(self, card_token, user):
        self.processor_backend.create_or_update_card(self, card_token, user)
        LOGGER.info('Updated card information for %s on processor '\
            '{"processor_card_key": %s}', self, self.processor_card_key)

    @method_decorator(transaction.atomic)
    def checkout(self, invoicables, user, token=None, remember_card=True):
        """
        *invoiced_items* is a set of ``Transaction`` that will be recorded
        in the ledger. Associated subscriptions will be updated such that
        the ends_at is extended in the future.
        """
        #pylint: disable=too-many-locals
        invoiced_items = []
        new_organizations = {}
        for invoicable in invoicables:
            subscription = invoicable['subscription']
            if not subscription.organization.id:
                # When the organization does not exist into the database,
                # we will create a random (i.e. hard to guess) one-time
                # 100% discount coupon that will be emailed to the expected
                # subscriber.
                if not subscription.plan in new_organizations:
                    new_organizations[subscription.plan] = []
                new_organizations[subscription.plan] += [
                    subscription.organization]
            else:
                LOGGER.info("[checkout] save subscription of %s to %s",
                    subscription.organization, subscription.plan)
                subscription.save()

            # If the invoicable we are checking out is somehow related to
            # a user shopping cart, we mark that cart item as recorded.
            cart_items = CartItem.objects.get_cart(user, plan=subscription.plan)
            if cart_items.exists():
                bulk_items = cart_items.filter(
                    email=subscription.organization.email)
                if bulk_items.exists():
                    cart_item = bulk_items.get()
                else:
                    cart_item = cart_items.get()
                cart_item.recorded = True
                cart_item.save()

        # At this point we have gathered all the ``Organization``
        # which have yet to be registered. For these no ``Subscription``
        # has been created yet. We create a 100% discount coupon that will
        # be emailed to the expected subscribers. We record the coupon
        # code as an event_id.
        coupons = {}
        for plan, absentees in new_organizations.iteritems():
            coupon = Coupon.objects.create(
                code=generate_random_slug(),
                organization=plan.organization,
                plan=plan,
                percent=100, nb_attempts=len(absentees),
                description='Bulk buying from %s (%s)' % (
                    self.printable_name, user))
            LOGGER.info('Auto-generated Coupon %s for %d subscriptions to %s',
                coupon.code, len(absentees), plan)
            coupons.update({plan: coupon})

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
                event_id = 'cpn_%s' % coupons[subscription.plan].code
            for invoiced_item in invoicable['lines']:
                invoiced_item.event_id = event_id
                invoiced_items += [invoiced_item]

        invoiced_items = Transaction.objects.execute_order(invoiced_items, user)
        charge = Charge.objects.charge_card(self, invoiced_items, user,
            token=token, remember_card=remember_card)

        # We email users which have yet to be registerd after the charge
        # is created, just that we don't inadvertently email new subscribers
        # in case something goes wrong.
        for plan, absentees in new_organizations.iteritems():
            for organization in absentees:
                signals.one_time_coupon_generated.send(
                    sender=__name__, subscriber=organization,
                    coupon=coupons[plan], user=user)

        return charge

    def remove_contributor(self, user):
        """
        Remove user as a contributor to organization.
        """
        relation = get_contributor_relation_model().objects.get(
            organization=self, user=user)
        relation.delete()

    def remove_manager(self, user):
        """
        Add user as a manager to organization.
        """
        relation = get_manager_relation_model().objects.get(
            organization=self, user=user)
        relation.delete()

    def retrieve_bank(self):
        """
        Returns associated bank account as a dictionnary.
        """
        return self.processor_backend.retrieve_bank(self)

    def retrieve_card(self):
        """
        Returns associated credit card.
        """
        return self.processor_backend.retrieve_card(self)

    def withdraw_available(self):
        available_amount, available_unit \
            = Transaction.objects.get_organization_balance(self)
        transfer_fee = self.processor_backend.prorate_transfer(available_amount)
        if available_amount > transfer_fee:
            available_amount -= transfer_fee
        else:
            available_amount = 0
        return (available_amount, available_unit)

    @method_decorator(transaction.atomic)
    def withdraw_funds(self, amount, user, created_at=None):
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
        funds_unit = 'usd' # XXX currency on receipient bank account
        created_at = datetime_or_now(created_at)
        descr = "withdraw from %s" % self.printable_name
        if user:
            descr += ' (%s)' % user.username
        # Execute transaction on processor first such that any processor
        # exception will be raised before we attempt to store
        # the ``Transaction``.
        processor_transfer_id, _ = self.processor_backend.create_transfer(
            self, amount, descr)
        Transaction.objects.create(
            event_id=processor_transfer_id,
            descr=descr,
            created_at=created_at,
            dest_unit=funds_unit,
            dest_amount=amount,
            dest_account=Transaction.WITHDRAW,
            dest_organization=self.processor,
            orig_unit=funds_unit,
            orig_amount=amount,
            orig_account=Transaction.FUNDS,
            orig_organization=self)
        # Add processor fee for transfer.
        transfer_fee = self.processor_backend.prorate_transfer(amount)
        self.create_processor_fee(transfer_fee, Transaction.FUNDS,
            event_id=processor_transfer_id, created_at=created_at)
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
            LOGGER.info('Created charge #%s of %d cents to %s',
                        charge.processor_key, charge.amount, customer)
        return charge


    def charge_card(self, customer, transactions, descr=None,
                    user=None, token=None, remember_card=True):
        #pylint: disable=too-many-arguments,too-many-locals
        """
        Create a charge on a customer card.

        Be careful, Stripe will not processed charges less than 50 cents.
        """
        amount, unit = sum_dest_amount(transactions)
        if amount == 0:
            return None
        provider = Transaction.objects.provider(transactions)
        processor = provider.processor
        processor_backend = get_processor_backend(processor)
        stmt_descr = provider.printable_name
        descr = DESCRIBE_CHARGED_CARD % {
            'charge': '', 'organization': customer.printable_name}
        if user:
            descr += ' (%s)' % user.username
        try:
            if token:
                if remember_card:
                    customer.update_card(card_token=token, user=user)
                    (processor_charge_id, created_at,
                     last4, exp_date) = processor_backend.create_charge(
                        customer, amount, unit, descr, stmt_descr)
                else:
                    (processor_charge_id, created_at,
                     last4, exp_date) = processor_backend.create_charge_on_card(
                        token, amount, unit, descr, stmt_descr)
            else:
                # XXX A card must already be attached to the customer.
                (processor_charge_id, created_at,
                 last4, exp_date) = processor_backend.create_charge(
                    customer, amount, unit, descr, stmt_descr)
            # Create record of the charge in our database
            descr = DESCRIBE_CHARGED_CARD % {'charge': processor_charge_id,
                'organization': customer.printable_name}
            if user:
                descr += ' (%s)' % user.username
            charge = self.create_charge(customer, transactions,
                amount, unit, processor, processor_charge_id, last4, exp_date,
                descr=descr, created_at=created_at)
        except CardError as err:
            # Expected runtime error. We just log that the charge was declined.
            LOGGER.info('CardError for charge of %d cents to %s: %s',
                        amount, customer, err)
            raise
        except ProcessorError as err:
            # An error from the processor which indicates the logic might be
            # incorrect, the network down, etc. We want to know about it right
            # away.
            LOGGER.exception('ProcessorError for charge of %d cents to %s: %s',
                        amount, customer, err)
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
    def line_items(self):
        """
        In most cases, use the ``line_items`` property instead of
        the ``charge_items`` because the order in which the records
        are returned is not guarenteed by SQL.
        This is important when identifying line items by an index.
        """
        return self.charge_items.order_by('id')

    @property
    def invoiced_total_amount(self):
        """
        Returns the total amount of all invoiced items.
        """
        amount, unit = sum_dest_amount(Transaction.objects.filter(
            invoiced_item__charge=self))
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

    def dispute_created(self):
        #pylint: disable=too-many-locals
        self.state = self.DISPUTED
        created_at = datetime_or_now()
        processor_backend = get_processor_backend(self.processor)
        previously_refunded, _ = sum_orig_amount(self.refunded)
        refund_available = self.amount - previously_refunded
        charge_available_amount, provider_unit, \
            charge_fee_amount, processor_unit \
            = processor_backend.charge_distribution(self)
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
                        processor_backend.dispute_fee(self.amount),
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
                provider:Receivable                      processor_fee
                processor:Backlog

            yyyy/mm/dd distribution to provider (backlog accounting)
                provider:Receivable                      distribute_amount
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
                cowork:Receivable                       $5.22
                stripe:Backlog

            2014/09/10 Charge ch_ABC123 distribution for open-space
                cowork:Receivable                     $174.77
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
        processor_backend = get_processor_backend(self.processor)
        total_distribute_amount, \
            funds_unit, \
            total_fee_amount, \
            processor_funds_unit = processor_backend.charge_distribution(self)

        charge_transaction = Transaction.objects.create(
            event_id=self.id,
            descr=self.description,
            created_at=self.created_at,
            dest_unit=processor_funds_unit,
            # XXX provider and processor must have same units.
            dest_amount=total_distribute_amount + total_fee_amount,
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
            event = invoiced_item.get_event()

            # If there is still an amount on the ``Payable`` account,
            # we create Payable to Liability transaction in order to correct
            # the accounts amounts. This is a side effect of the atomicity
            # requirement for a ``Transaction`` associated to a ``Charge``.
            balance_payable, _ = \
                Transaction.objects.get_subscription_balance(
                    event, Transaction.PAYABLE)
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

            provider = event.provider
            charge_item_amount = invoiced_item.dest_amount
            # Has long as we have only one item and charge/funds are using
            # same unit, multiplication and division are carefully crafted
            # to keep full precision.
            # XXX to check with transfer btw currencies and multiple items.
            orig_fee_amount = (charge_item_amount *
                total_fee_amount / (total_distribute_amount + total_fee_amount))
            orig_distribute_amount = charge_item_amount - orig_fee_amount
            fee_amount = ((total_fee_amount * charge_item_amount / self.amount))
            distribute_amount = (
                total_distribute_amount * charge_item_amount / self.amount)
            if fee_amount > 0:
                # Example:
                # 2014/01/15 fee to cowork
                #     cowork:Receivable                             900
                #     stripe:Backlog
                charge_item.invoiced_fee = Transaction.objects.create(
                    created_at=self.created_at,
                    descr=DESCRIBE_CHARGED_CARD_PROCESSOR % {
                        'charge': self.processor_key, 'event': event},
                    event_id=self.id,
                    dest_unit=self.unit,
                    dest_amount=orig_fee_amount,
                    dest_account=Transaction.RECEIVABLE,
                    dest_organization=provider,
                    orig_unit=processor_funds_unit,
                    orig_amount=fee_amount,
                    orig_account=Transaction.BACKLOG,
                    orig_organization=self.processor)
                charge_item.save()
                # pylint:disable=no-member
                self.processor.funds_balance += fee_amount
                self.processor.save()

            # Example:
            # 2014/01/15 distribution due to cowork
            #     cowork:Receivable                             8000
            #     cowork:Backlog
            #
            # 2014/01/15 distribution due to cowork
            #     cowork:Funds                                  8000
            #     stripe:Funds
            Transaction.objects.create(
                event_id=self.id,
                created_at=self.created_at,
                descr=DESCRIBE_CHARGED_CARD_PROVIDER % {
                        'charge': self.processor_key, 'event': event},
                dest_unit=self.unit,
                dest_amount=orig_distribute_amount,
                dest_account=Transaction.RECEIVABLE,
                dest_organization=provider,
                orig_unit=funds_unit,
                orig_amount=distribute_amount,
                orig_account=Transaction.BACKLOG,
                orig_organization=provider)

            Transaction.objects.create(
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

    @property
    def provider(self):
        """
        If all the invoiced items on this charge are related to the same
        provider, returns that ``Organization`` otherwise returns the site
        owner.
        """
        #pylint: disable=no-member
        return Transaction.objects.provider([charge_item.invoiced
                         for charge_item in self.charge_items.all()])

    def refund(self, linenum, refunded_amount=None, created_at=None):
        # XXX We donot currently supply a *description* for the refund.
        #pylint:disable=too-many-locals
        assert self.state == self.DONE

        # We do all computation and checks before starting to modify
        # the database to minimize the chances of getting into
        # an inconsistent state.
        processor_backend = get_processor_backend(self.processor)
        #pylint: disable=no-member
        charge_item = self.line_items[linenum]
        invoiced_item = charge_item.invoiced
        if refunded_amount is None:
            refunded_amount = invoiced_item.dest_amount

        previously_refunded, _ = sum_orig_amount(self.refunded)
        refund_available = invoiced_item.dest_amount - previously_refunded
        if refunded_amount > refund_available:
            raise InsufficientFunds("Cannot refund %(refund_required)s"\
" while there is only %(refund_available)s available on the line item."
% {'refund_available': as_money(abs(refund_available), self.unit),
   'refund_required': as_money(abs(refunded_amount), self.unit)})

        charge_available_amount, provider_unit, \
            charge_fee_amount, processor_unit \
            = processor_backend.charge_distribution(self)

        # We execute the refund on the processor backend here such that
        # the following call to ``processor_backend.charge_distribution``
        # returns the correct ``corrected_available_amount`` and
        # ``corrected_fee_amount``.
        processor_backend.refund_charge(self, refunded_amount)

        corrected_available_amount, provider_unit, \
            corrected_fee_amount, processor_unit \
            = processor_backend.charge_distribution(
                self, refunded=previously_refunded + refunded_amount)

        charge_item.create_refund_transactions(
            refunded_amount, charge_available_amount, charge_fee_amount,
            corrected_available_amount, corrected_fee_amount,
            created_at=created_at,
            provider_unit=provider_unit, processor_unit=processor_unit)
        signals.charge_updated.send(sender=__name__, charge=self, user=None)

    def retrieve(self):
        """
        Retrieve the state of charge from the processor.
        """
        processor_backend = get_processor_backend(self.processor)
        processor_backend.retrieve_charge(self)
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
        if not processor_unit:
            processor_unit = 'usd' # XXX
        if not provider_unit:
            provider_unit = 'usd' # XXX
        refunded_fee_amount = 0
        if invoiced_fee:
            # Implementation Note: There is a fixed 30 cents component
            # to the processor fee. We must recompute the corrected
            # fee on the total amount left over after the refund.
            refunded_fee_amount = (
                (charge_fee_amount - corrected_fee_amount)
                * invoiced_item.dest_amount / charge.amount)
        # ``corrected_available_amount`` is in provider unit,
        # ``invoiced_item.dest_amount`` and ``self.amount`` are in subscriber
        # unit, thus ``refunded_distribute_amount`` is the actual amount
        # that should be given back from the distribution to the provider
        # once the refund is processed.
        refunded_distribute_amount = (
            (charge_available_amount - corrected_available_amount)
            * invoiced_item.dest_amount / charge.amount)

        LOGGER.info("Refund charge %s for %d (%s)"\
            " (distributed: %d (%s), processor fee: %d (%s))",
            charge.processor_key, refunded_amount, charge.unit,
            refunded_distribute_amount, provider_unit,
            refunded_fee_amount, processor_unit)

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


class Coupon(models.Model):
    """
    Coupons are used on invoiced to give a rebate to a customer.
    """
    #pylint: disable=super-on-old-class
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
    QUATERLY = 5
    YEARLY = 7

    INTERVAL_CHOICES = [
        (HOURLY, "HOURLY"),
        (DAILY, "DAILY"),
        (WEEKLY, "WEEKLY"),
        (MONTHLY, "MONTHLY"),
        (QUATERLY, "QUATERLY"),
        (YEARLY, "YEARLY"),
        ]

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=50, null=True)
    description = models.TextField()
    is_active = models.BooleanField(default=False)
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
    unlock_event = models.CharField(max_length=128, null=True, blank=True,
        help_text=_('Payment required to access full service'))
    advance_discount = models.PositiveIntegerField(default=0,
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

    def end_of_period(self, start_time, nb_periods=1):
        result = start_time
        if nb_periods:
            # In case of a ``SETTLED``, *nb_periods* will be ``None``
            # since the description does not (should not) allow us to
            # extend the subscription length.
            if self.interval == self.HOURLY:
                result += datetime.timedelta(hours=1 * nb_periods)
            elif self.interval == self.DAILY:
                result += datetime.timedelta(days=1 * nb_periods)
            elif self.interval == self.WEEKLY:
                result += datetime.timedelta(days=7 * nb_periods)
            elif self.interval == self.MONTHLY:
                result += relativedelta(months=1 * nb_periods)
            elif self.interval == self.QUATERLY:
                result += relativedelta(months=3 * nb_periods)
            elif self.interval == self.YEARLY:
                result += relativedelta(years=1 * nb_periods)
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
        elif self.interval == self.QUATERLY:
            result = '%d months' % (3 * nb_periods)
        elif self.interval == self.YEARLY:
            result = '%d year' % nb_periods
        if nb_periods > 1:
            result += 's'
        return result

    def period_number(self, text):
        """
        This method is the reverse of ``humanize_period``. It will extract
        a number of periods from a text.
        """
        result = None
        if self.interval == self.HOURLY:
            pat = r'(\d+) hour'
        elif self.interval == self.DAILY:
            pat = r'(\d+) day'
        elif self.interval == self.WEEKLY:
            pat = r'(\d+) week'
        elif self.interval == self.MONTHLY:
            pat = r'(\d+) month'
        elif self.interval == self.QUATERLY:
            pat = r'(\d+) months'
        elif self.interval == self.YEARLY:
            pat = r'(\d+) year'
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
        elif self.interval in [self.MONTHLY, self.QUATERLY]:
            # Monthly and Quaterly: fractional period is in days.
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
        related_name='cart_items',
        help_text=_("user who added the item to the cart."))
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
    objects = SubscriptionManager()

    auto_renew = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ends_at = models.DateTimeField()
    description = models.TextField(null=True, blank=True)
    organization = models.ForeignKey(Organization)
    plan = models.ForeignKey(Plan)

    def __unicode__(self):
        return '%s-%s' % (unicode(self.organization), unicode(self.plan))

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
        return (lower, min(upper, self.ends_at))


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
                estimated = delta.days / 30
            elif self.plan.interval == Plan.QUATERLY:
                estimated = delta.days / (30 + 31 + 30)
            elif self.plan.interval == Plan.YEARLY:
                estimated = delta.days / 365
            upper = self.plan.end_of_period(start_upper, nb_periods=estimated)
            if upper < until_lower:
                full_periods = estimated + 1
            else:
                full_periods = estimated
        else:
            full_periods = 0
        # partial-at-start + full periods + partial-at-end
        return ((start_upper - start).total_seconds()
                / (start_upper - start_lower).total_seconds()
                + full_periods
                + (until - until_lower).total_seconds()
                / (until_upper - until_lower).total_seconds())

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
                     orig_account=Transaction.PAYABLE).order_by(
                     '-created_at')

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
              & Q(dest_account=account)))) \
            .order_by('-created_at')

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
            dest_organization=organization, **kwargs)

    def get_organization_balance(self, organization,
                                 account=None, until=None, **kwargs):
        """
        Returns the balance on an organization's account (by default:
        ``FUNDS``).
        """
        until = datetime_or_now(until)
        if not account:
            account = Transaction.FUNDS
        dest_amount, dest_unit = sum_dest_amount(self.filter(
            dest_organization=organization, dest_account__startswith=account,
            created_at__lt=until, **kwargs))
        orig_amount, orig_unit = sum_orig_amount(self.filter(
            orig_organization=organization, orig_account__startswith=account,
            created_at__lt=until, **kwargs))
        if dest_unit is None:
            unit = orig_unit
        elif orig_unit is None:
            unit = dest_unit
        elif dest_unit != orig_unit:
            raise ValueError('orig and dest balances until %s for account'\
' %s of %s have different unit (%s vs. %s).' % (until, account, organization,
                orig_unit, dest_unit))
        else:
            unit = dest_unit
        return dest_amount - orig_amount, unit

    def get_statement_balance(self, organization, until=None):
        until = datetime_or_now(until)
        dest_amount, dest_unit = sum_dest_amount(self.filter(
            Q(dest_account=Transaction.PAYABLE)
            | Q(dest_account=Transaction.LIABILITY),
            dest_organization=organization,
            created_at__lt=until))
        orig_amount, orig_unit = sum_orig_amount(self.filter(
            Q(orig_account=Transaction.PAYABLE)
            | Q(orig_account=Transaction.LIABILITY),
            orig_organization=organization,
            created_at__lt=until))
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
        dest_amount, dest_unit = sum_dest_amount(
            self.get_invoiceables(subscription.organization).filter(
                event_id=subscription.id))
        return dest_amount, dest_unit

    def get_subscription_balance(self, subscription, account,
                                 starts_at=None, ends_at=None):
        """
        Returns the balance on a *subscription* for an *account*
        for the period [*starts_at*, *ends_at*[ as a tuple (amount, unit).
        """
        kwargs = {}
        if starts_at:
            kwargs.update({'created_at__gte': starts_at})
        if ends_at:
            kwargs.update({'created_at__lt': ends_at})
        dest_amount, dest_unit = sum_dest_amount(self.filter(
            dest_account=account, event_id=subscription.id, **kwargs))
        orig_amount, orig_unit = sum_orig_amount(self.filter(
            orig_account=account, event_id=subscription.id, **kwargs))
        if dest_unit is None:
            unit = orig_unit
        elif orig_unit is None:
            unit = dest_unit
        elif dest_unit != orig_unit:
            raise ValueError('orig and dest balances for subscription %s'\
' have different unit (%s vs. %s).' % (subscription, orig_unit, dest_unit))
        else:
            unit = dest_unit
        return dest_amount - orig_amount, unit

    def get_subscription_income_balance(self, subscription,
                                        starts_at=None, ends_at=None):
        """
        Returns the recognized income balance on a subscription
        for the period [starts_at, ends_at[ as a tuple (amount, unit).
        """
        return self.get_subscription_balance(
            subscription, Transaction.INCOME,
            starts_at=starts_at,
            ends_at=ends_at)

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
    def new_subscription_order(subscription, nb_periods, prorated_amount=0,
        created_at=None, descr=None, discount_percent=0,
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
        if not descr:
            amount = int((prorated_amount
                + (subscription.plan.period_amount * nb_periods))
                * (100 - discount_percent) / 100)
            ends_at = subscription.plan.end_of_period(
                subscription.ends_at, nb_periods)
            descr = describe_buy_periods(subscription.plan, ends_at, nb_periods,
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
                                 amount=None, at_time=None, descr=None):
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
        created_transactions = []
        created_at = datetime_or_now(at_time)
        backlog_amount, _ = self.get_organization_balance(
            subscription.plan.organization, account=Transaction.BACKLOG,
            event_id=subscription.id)
        receivable_amount, _ = self.get_organization_balance(
            subscription.plan.organization, account=Transaction.RECEIVABLE,
            event_id=subscription.id)
        receivable_amount = abs(receivable_amount) # direction
        if backlog_amount > 0:
            available = min(amount, backlog_amount)
            created_transactions += [self.create(
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
                orig_organization=subscription.plan.organization)]
            amount -= backlog_amount
        if receivable_amount > 0:
            available = min(amount, receivable_amount)
            created_transactions += [self.create(
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
                orig_organization=subscription.plan.organization)]
            amount -= available
        assert amount == 0
        return created_transactions

    @staticmethod
    def provider(invoiced_items):
        """
        If all subscriptions referenced by *invoiced_items* are to the same
        provider, return it otherwise return the site owner.
        """
        result = None
        for invoiced_item in invoiced_items:
            event = invoiced_item.get_event()
            if event:
                if not result:
                    result = event.provider
                elif result != event.provider:
                    result = get_current_provider()
                    break
        if not result:
            result = get_current_provider()
        return result


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

    orig_account = models.CharField(max_length=30, default="unknown")
    orig_organization = models.ForeignKey(Organization,
        related_name="outgoing")
    orig_amount = models.PositiveIntegerField(default=0,
        help_text=_('amount withdrawn from origin in origin units'))
    orig_unit = models.CharField(max_length=3, default="usd",
        help_text=_('Measure of units on origin account'))

    dest_account = models.CharField(max_length=30, default="unknown")
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
        try:
            return Subscription.objects.get(id=self.event_id)
        except ValueError:
            if self.event_id.startswith('cpn_'):
                return Coupon.objects.get(code=self.event_id[4:])
        return None


def get_current_provider():
    """
    Returns the site-wide provider from a request.
    """
    if settings.PROVIDER_CALLABLE:
        from saas.compat import import_string
        provider_slug = str(import_string(settings.PROVIDER_CALLABLE)())
        LOGGER.debug("saas: get_current_provider('%s')", provider_slug)
        return Organization.objects.get(slug=provider_slug)
    return Organization.objects.get(pk=settings.PROVIDER_ID)


def sum_dest_amount(transactions):
    """
    Return the sum of the amount in the *transactions* set.
    """
    query_result = []
    if isinstance(transactions, QuerySet):
        if transactions.exists():
            query_result = transactions.values(
                'dest_unit').annotate(Sum('dest_amount'))
    else:
        group_by = {}
        for item in transactions:
            if not item.dest_unit in group_by:
                group_by[item.dest_unit] = 0
            group_by[item.dest_unit] += item.dest_amount
        for unit, amount in group_by.iteritems():
            query_result += [{'dest_unit': unit, 'dest_amount__sum': amount}]
    if len(query_result) > 0:
        if len(query_result) > 1:
            try:
                raise ValueError("sum accross %d units (%s)" %
                    (len(query_result), ','.join(
                        [res['dest_unit'] for res in query_result])))
            except ValueError as err:
                LOGGER.exception(err)
        # XXX Hack: until we change the function signature
        return query_result[0]['dest_amount__sum'], query_result[0]['dest_unit']
    return 0, None


def sum_orig_amount(transactions):
    """
    Return the sum of the amount in the *transactions* set.
    """
    query_result = []
    if isinstance(transactions, QuerySet):
        if transactions.exists():
            query_result = transactions.values(
                'orig_unit').annotate(Sum('orig_amount'))
    else:
        group_by = {}
        for item in transactions:
            if not item.orig_unit in group_by:
                group_by[item.orig_unit] = 0
            group_by[item.orig_unit] += item.orig_amount
        for unit, amount in group_by.iteritems():
            query_result += [{'orig_unit': unit, 'orig_amount__sum': amount}]
    if len(query_result) > 0:
        if len(query_result) > 1:
            try:
                raise ValueError("sum accross %d units (%s)" %
                    (len(query_result), ', '.join(
                        [res['orig_unit'] for res in query_result])))
            except ValueError as err:
                LOGGER.exception(err)
        # XXX Hack: until we change the function signature
        return query_result[0]['orig_amount__sum'], query_result[0]['orig_unit']
    return 0, None
