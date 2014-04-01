# Copyright (c) 2014, Fortylines LLC
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

import datetime, logging

from dateutil.relativedelta import relativedelta
from django.db import IntegrityError, models, transaction
from django.db.models import Sum
from django.db.models.query import QuerySet
from django.utils.timezone import utc
from django.utils.translation import ugettext_lazy as _
from django.utils.decorators import method_decorator
from stripe.error import InvalidRequestError

from saas import settings
from saas import signals
from saas import get_manager_relation_model, get_contributor_relation_model
from saas.humanize import as_money, describe_buy_periods, DESCRIBE_BALANCE

LOGGER = logging.getLogger(__name__)


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

    def associate_processor(self, customer, card=None):
        import saas.backends as backend # avoid import loop
        if not isinstance(customer, Organization):
            if isinstance(customer, basestring):
                customer = self.get(slug=customer)
            else:
                customer = self.get(pk=customer)
        if not customer.processor_id:
            # We don't have a processor_id yet for this customer,
            # so let's create one.
            customer.processor_id = backend.create_customer(
                customer.slug, card)
            customer.save()
            LOGGER.info('Created customer #%s for %s on processor',
                        customer.processor_id, customer)
        else:
            backend.update_card(customer, card)
            signals.card_updated.send(customer)

    def get_organization(self, organization):
        """Returns an ``Organization`` instance from the organization
        parameter which could either be an id or a slug.

        In case organization is None, this method returns the site owner.
        """
        if organization is None:
            return self.get_site_owner()
        if not isinstance(organization, Organization):
            return self.get(slug=organization)
        return organization

    def get_site_owner(self):
        return self.get(pk=settings.SITE_ID)

    def find_contributed(self, user):
        """
        Returns a QuerySet of Organziation for which the user is a contributor.
        """
        return self.filter(contributors__id=user.id)

    def find_managed(self, user):
        """
        Returns a QuerySet of Organziation for which the user is a manager.
        """
        return self.filter(managers__id=user.id)

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
    full_name = models.CharField(_('full name'), max_length=60, blank=True)
    # contact by e-mail
    email = models.EmailField(
        help_text=_("Contact email for support related to the organization."))
    # contact by phone
    phone = models.CharField(max_length=50,
        help_text=_("Contact phone for support related to the organization."))
    # contact by physical mail
    street_address = models.CharField(max_length=150)
    locality = models.CharField(max_length=50)
    region = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=50)
    country_name = models.CharField(max_length=75)

    belongs = models.ForeignKey('Organization', null=True)
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
    processor = models.CharField(null=True, max_length=20)
    processor_id = models.CharField(null=True,
        blank=True, max_length=20)
    processor_recipient_id = models.CharField(
        null=True, blank=True, max_length=20,
        help_text=_("Used to deposit funds to the organization bank account"))

    def __unicode__(self):
        return unicode(self.slug)

    def add_contributor(self, user):
        """
        Add user as a contributor to organization.
        """
        relation = get_contributor_relation_model()(
            organization=self, user=user)
        relation.save()

    def add_manager(self, user):
        """
        Add user as a manager to organization.
        """
        relation = get_manager_relation_model()(
            organization=self, user=user)
        relation.save()

    def associate_bank(self, bank_token):
        import saas.backends as backend # avoid import loop
        backend.create_or_update_bank(self, bank_token)
        signals.bank_updated.send(self)

    @method_decorator(transaction.atomic)
    def checkout(self, invoicables, user, token=None, remember_card=True):
        """
        *invoiced_items* is a set of ``Transaction`` that will be recorded
        in the ledger. Associated subscriptions will be updated such that
        the ends_at is extended in the future.
        """
        invoiced_items = []
        for invoicable in invoicables:
            subscription = invoicable['subscription']
            assert subscription.organization == self
            lines = invoicable['lines']
            if len(lines) > 0:
                # Otherwise there is nothing to invoice for the subscription.
                if not subscription.id:
                    subscription.save()
                    cart_items = CartItem.objects.filter(
                        user=user, plan=subscription.plan, recorded=False)
                    if cart_items.exists():
                        cart_item = cart_items.get()
                        cart_item.recorded = True
                        cart_item.save()
                for invoiced_item in invoicable['lines']:
                    # We can't set the event_id until the subscription is saved
                    # in the database.
                    invoiced_item.orig_units = subscription.id
                    invoiced_item.event_id = subscription.id
                    invoiced_items += [invoiced_item]

        invoiced_items = Transaction.objects.execute_order(invoiced_items)
        return Charge.objects.charge_card(
            self, invoiced_items, user,
            token=token, remember_card=remember_card)

    @method_decorator(transaction.atomic)
    def withdraw_funds(self, amount, user, created_at=None):
        """
        Withdraw funds from the site into the organization's bank account.

        This will create two transactions. For example:

        2014/01/31 00:00:00 #hosting - distribution to cowork
            djaodjin:Expenses                            6000
            djaodjin:Funds

        2014/01/31 00:00:00 #hosting - distribution to cowork
            cowork:Funds                                 6000
            djaodjin:Payable
        """
        import saas.backends as backend # avoid import loop
        if not created_at:
            created_at = datetime.datetime.utcnow().replace(tzinfo=utc)
        try:
            provider_subscription = Subscription.objects.get(
                organization=self,
                plan__organization=Organization.objects.get_site_owner())
            processor = provider_subscription.plan.organization
            provider_subscription_id = provider_subscription.id
        except Subscription.DoesNotExist:
            processor = Organization.objects.get_site_owner()
            provider_subscription_id = None
        descr = "withdraw from %s" % self.full_name
        if user:
            descr += ' (%s)' % user.username
        # Execute transaction on backend first
        processor_transfer_id, _ = backend.create_transfer(self, amount, descr)
        # payment
        Transaction.objects.create(
            event_id=processor_transfer_id,
            descr=descr,
            created_at=created_at,
            orig_amount=amount,
            orig_account=Transaction.PAYABLE,
            orig_organization=processor,
            dest_amount=amount,
            dest_account=Transaction.FUNDS,
            dest_organization=self)
        descr = "withdraw by %s" % self.full_name
        if user:
            descr += ' (%s)' % user.username
        # expense
        Transaction.objects.create(
            event_id=provider_subscription_id,
            descr=descr,
            created_at=created_at,
            orig_amount=amount,
            orig_account=Transaction.FUNDS,
            orig_organization=processor,
            dest_amount=amount,
            dest_account=Transaction.EXPENSES,
            dest_organization=processor)


class Agreement(models.Model):

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=150, unique=True)
    modified = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return unicode(self.slug)


class SignatureManager(models.Manager):

    def create_signature(self, agreement, user):
        if isinstance(agreement, basestring):
            agreement = Agreement.objects.get(slug=agreement)
        try:
            sig = self.get(agreement=agreement, user=user)
            sig.last_signed = datetime.datetime.now()
            sig.save()
        except Signature.DoesNotExist:
            sig = self.create(
                agreement=agreement, user=user)
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='user_id')

    class Meta:
        unique_together = ('agreement', 'user')

    def __unicode__(self):
        return '%s-%s' % (self.user, self.agreement)


class CartItemManager(models.Manager):

    def get_cart(self, user):
        return self.filter(user=user, recorded=False)


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
    """
    objects = CartItemManager()

    created_at = models.DateTimeField(auto_now_add=True,
        help_text=_("date/time at which the item was added to the cart."))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='user_id',
        help_text=_("user who added the item to the cart."))
    plan = models.ForeignKey('Plan',
        help_text=_("item added to the cart."))
    recorded = models.BooleanField(default=False,
        help_text=_("whever the item has been checked out or not."))

    class Meta:
        unique_together = ('user', 'plan')

    def __unicode__(self):
        return '%s-%s' % (self.user, self.plan)


class ChargeManager(models.Manager):

    def charge_card(self, customer, transactions, descr=None,
                    user=None, token=None, remember_card=True):
        """
        Create a charge on a customer card.
        """
        # Be careful, stripe will not processed charges less than 50 cents.
        import saas.backends as backend # Avoid import loop
        amount = sum_dest_amount(transactions)
        descr = 'charged credit card of %s' % customer.full_name
        if user:
            descr += ' (%s)' % user.username
        try:
            if token:
                if remember_card:
                    Organization.objects.associate_processor(
                        customer, card=token)
                    (processor_charge_id, created_at,
                     last4, exp_date) = backend.create_charge(
                        customer, amount, descr)
                else:
                    (processor_charge_id, created_at,
                     last4, exp_date) = backend.create_charge_on_card(
                        token, amount, descr)
            else:
                (processor_charge_id, created_at,
                 last4, exp_date) = backend.create_charge(
                    customer, amount, descr)
            # Create record of the charge in our database
            charge = self.create(
                processor_id=processor_charge_id, amount=amount,
                created_at=created_at, description=descr,
                customer=customer, last4=last4, exp_date=exp_date)
            charge.invoiced_items.add(*transactions) #pylint: disable=star-args
            charge.save()
            LOGGER.info('Created charge #%s of %d cents to %s',
                        charge.processor_id, charge.amount, customer)
        except InvalidRequestError:
            LOGGER.info('InvalidRequestError for charge of %d cents to %s',
                        amount, customer)
            charge = None
        return charge

    def last_charge(self, subscription):
        """
        Returns the last charge for a subscription.
        """
        queryset = self.filter(
            invoiced_items__event_id=subscription.id).order_by('-created_at')
        if queryset.exists():
            return queryset.first()
        return None


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
    amount = models.IntegerField(default=0, help_text="Amount in cents")
    customer = models.ForeignKey(Organization,
        help_text='organization charged')
    invoiced_items = models.ManyToManyField(
        'Transaction', related_name='charges',
        help_text="transactions invoiced through this charge")
    description = models.TextField(null=True)
    last4 = models.IntegerField()
    exp_date = models.DateField()
    processor = models.SlugField()
    processor_id = models.SlugField(unique=True, db_index=True)
    state = models.SmallIntegerField(choices=CHARGE_STATES, default=CREATED)

    # XXX unique together paid and invoiced.
    # customer and invoiced_items account payble should match.

    def __unicode__(self):
        return unicode(self.processor_id)

    @property
    def invoiced_total_amount(self):
        """
        Returns the total amount of all invoiced items.
        """
        return sum_dest_amount(self.invoiced_items.all())

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

    def capture(self):
        # XXX Create transaction
        pass

    @method_decorator(transaction.atomic)
    def payment_successful(self):
        """
        When a charge through the payment processor is sucessful, a transaction
        is created from client payable to processor assets. The amount of the
        charge is then redistributed to the providers (minus processor fee).
        """
        self.state = self.DONE
        self.save()

        # Example:
        # 2014/01/15 00:00:00 charge on xia card
        #     xia:Expenses                                 13800
        #     djaodjin:Income
        charge_transaction = Transaction.objects.create(
            event_id=self.id,
            descr=self.description,
            created_at=self.created_at,
            orig_amount=self.amount,
            orig_account=Transaction.INCOME,
            orig_organization=Organization.objects.get_site_owner(),
            dest_amount=self.amount,
            dest_account=Transaction.EXPENSES,
            dest_organization=self.customer)
        # Once we have created a transaction for the charge, let's
        # redistribute the money to the rightful owners.
        for item in self.invoiced_items.all():
            subscription = Subscription.objects.get(pk=item.event_id)
            customer = subscription.organization
            provider = subscription.plan.organization
            try:
                provider_subscription = Subscription.objects.get(
                    organization=subscription.plan.organization,
                    plan__organization=Organization.objects.get_site_owner())
                processor = provider_subscription.plan.organization
                provider_subscription_id = provider_subscription.id
                fee_amount = provider_subscription.plan.prorate_transaction(
                    item.dest_amount)
            except Subscription.DoesNotExist:
                processor = Organization.objects.get_site_owner()
                provider_subscription_id = None
                fee_amount = 0
            distribute_amount = item.dest_amount - fee_amount
            if fee_amount > 0:
                # Example:
                # 2014/01/15 00:00:00 #hosting - fee to cowork
                #           cowork:Expenses                                900
                #           djaodjin:Funds
                Transaction.objects.create(
                    event_id=provider_subscription_id,
                    descr="Processing fee for %s" % subscription,
                    created_at=self.created_at,
                    orig_amount=fee_amount,
                    orig_account=Transaction.FUNDS,
                    orig_organization=processor,
                    dest_amount=fee_amount,
                    dest_account=Transaction.EXPENSES,
                    dest_organization=provider)
            # Example:
            # 2014/01/15 00:00:00 #hosting - distribution due to cowork
            #           djaodjin:Payable                              6000
            #           cowork:Funds
            Transaction.objects.create(
                event_id=provider_subscription_id,
                descr="distribution due to %s" % provider,
                created_at=self.created_at,
                orig_amount=distribute_amount,
                orig_account=Transaction.FUNDS,
                orig_organization=provider,
                dest_amount=distribute_amount,
                dest_account=Transaction.PAYABLE,
                dest_organization=processor)
            # Example:
            # 2014/01/15 00:00:00 #desk - payment for subscription
            #           djaodjin:Funds                                6900
            #           xia:Payable
            Transaction.objects.create(
                event_id=subscription.id,
                descr="payment for %s" % subscription.plan,
                created_at=self.created_at,
                orig_amount=item.dest_amount,
                orig_account=Transaction.PAYABLE,
                orig_organization=customer,
                dest_amount=item.dest_amount,
                dest_account=Transaction.FUNDS,
                dest_organization=processor)
        if self.invoiced_total_amount > self.amount:
            #pylint: disable=nonstandard-exception
            raise IntegrityError("The total amount of invoiced items for "\
              "charge %s exceed the amount of the charge.", self.processor_id)
        return charge_transaction

    def refund(self, amount=0, description=None, created_at=None):
        """
        Partially refund the charge.
        """
        if not created_at:
            created_at = datetime.datetime.utcnow().replace(tzinfo=utc)
        # XXX fix
        Transaction.objects.create(
            created_at=created_at,
            orig_amount=amount,
            orig_organization=Organization.objects.get_site_owner(),
            orig_account=Transaction.FUNDS,
            dest_organization=Organization.objects.get_site_owner(),
            dest_account=Transaction.REFUND,
            dest_amount=amount,
            descr=description,
            event_id=self.processor_id)
        Transaction.objects.create(
            created_at=created_at,
            orig_amount=amount,
            orig_organization=Organization.objects.get_site_owner(),
            orig_account=Transaction.REFUND,
            dest_organization=self.customer,
            dest_account=Transaction.FUNDS,
            dest_amount=amount,
            descr=description,
            event_id=self.processor_id)


class Coupon(models.Model):
    """
    Coupons are used on invoiced to give a rebate to a customer.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, db_column='user_id', null=True)
    customer = models.ForeignKey(Organization, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    code = models.SlugField(primary_key=True, db_index=True)
    percent = models.IntegerField(help_text="Percentage discounted")
    redeemed = models.BooleanField(default=False)

    def __unicode__(self):
        return '%s-%s' % (self.user, self.code)


class Plan(models.Model):
    """
    Recurring billing plan
    """
    UNSPECIFIED = 0
    HOURLY = 1
    DAILY = 2
    WEEKLY = 3
    MONTHLY = 4
    QUATERLY = 5
    YEARLY = 7

    INTERVAL_CHOICES = [
        (UNSPECIFIED, "UNSPECIFIED"), # XXX Appears in drop down boxes
        (HOURLY, "HOURLY"),
        (DAILY, "DAILY"),
        (WEEKLY, "WEEKLY"),
        (MONTHLY, "MONTHLY"),
        (QUATERLY, "QUATERLY"),
        (YEARLY, "YEARLY"),
        ]

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=50)
    description = models.TextField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    discontinued_at = models.DateTimeField(null=True, blank=True)
    organization = models.ForeignKey(Organization)
    setup_amount = models.IntegerField(default=0,
        help_text=_('One-time charge amount (in cents).'))
    period_amount = models.IntegerField(default=0,
        help_text=_('Recurring amount per period (in cents).'))
    transaction_fee = models.IntegerField(default=0,
        help_text=_('Fee per transaction (in per 10000).'))
    interval = models.IntegerField(choices=INTERVAL_CHOICES)
    unlock_event = models.CharField(max_length=128,
        help_text=_('Payment required to access full service'))
    # end game
    length = models.IntegerField(null=True, blank=True,
        help_text=_('Number of intervals the plan before the plan ends.'))
    # Pb with next : maybe create an other model for it
    next_plan = models.ForeignKey("Plan", null=True)

    class Meta:
        unique_together = ('slug', 'organization')

    def __unicode__(self):
        return unicode(self.slug)

    def end_of_period(self, start_time, nb_periods=1):
        result = start_time
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

    def prorate_transaction(self, amount):
        """
        Return the fee associated to a transaction.
        """
        return amount * self.transaction_fee / 10000

    def prorate_period(self, start_time, end_time):
        """
        Return the pro-rate recurring amount for a period
        [start_time, end_time[.

        If end_time - start_time >= interval period, the value
        returned is undefined.
        """
        if self.interval == 1:
            # Hourly: fractional period is in minutes.
            fraction = (end_time - start_time).seconds / 3600
        elif self.interval == 2:
            # Daily: fractional period is in hours.
            fraction = ((end_time - start_time).seconds
                        / (3600 * 24))
        elif self.interval == 3:
            # Weekly, fractional period is in days.
            fraction = (end_time.date() - start_time.date()).days / 7
        elif self.interval in [4, 5]:
            # Monthly and Quaterly: fractional period is in days.
            # We divide by the maximum number of days in a month to
            # the advantage of a customer.
            fraction = (end_time.date() - start_time.date()).days / 31
        elif self.interval == 7:
            # Yearly: fractional period is in days.
            # We divide by the maximum number of days in a year to
            # the advantage of a customer.
            fraction = (end_time.date() - start_time.date()).days / 366
        # Round down to the advantage of a customer.
        return int(self.period_amount * fraction)


class SubscriptionManager(models.Manager):
    #pylint: disable=super-on-old-class

    def active_for(self, organization, ends_at=None):
        """
        Returns active subscriptions for *organization*
        """
        if not ends_at:
            ends_at = datetime.datetime.utcnow().replace(tzinfo=utc)
        return self.filter(organization=organization, ends_at__gt=ends_at)

    def create(self, **kwargs):
        if not kwargs.has_key('ends_at'):
            start_time = datetime.datetime.utcnow().replace(tzinfo=utc)
            plan = kwargs.get('plan')
            return super(SubscriptionManager, self).create(
                ends_at=plan.end_of_period(start_time), **kwargs)
        return super(SubscriptionManager, self).create(**kwargs)

    def new_instance(self, organization, plan, ends_at=None):
        #pylint: disable=no-self-use
        """
        New ``Subscription`` instance which is explicitely not in the db.
        """
        return Subscription(
            organization=organization, plan=plan, ends_at=ends_at)


class Subscription(models.Model):
    """
    Subscriptions of an Organization to a Plan
    """
    objects = SubscriptionManager()

    created_at = models.DateTimeField(auto_now_add=True)
    ends_at = models.DateTimeField()
    organization = models.ForeignKey('Organization')
    plan = models.ForeignKey('Plan')

    class Meta:
        unique_together = ('organization', 'plan')

    def __unicode__(self):
        return '%s-%s' % (unicode(self.organization), unicode(self.plan))

    @property
    def is_locked(self):
        return Transaction.objects.get_subscription_balance(self) > 0

    def use_of_service(self, nb_periods, prorated_amount=0,
        created_at=None, descr=None, discount_percent=None):
        """
        Each time a provider delivers a service to a client, a transaction
        is recorded that goes from the provider ``Income`` account to
        the client ``Payable`` account.
        """
        if not descr:
            amount = int(
                (prorated_amount + (self.plan.period_amount * nb_periods))
                * (100 - discount_percent) / 100)
            ends_at = self.plan.end_of_period(self.ends_at, nb_periods)
            descr = describe_buy_periods(self.plan, ends_at, nb_periods)
            if discount_percent:
                descr += ' - a %d%% discount' % discount_percent
        else:
            # If we already have a description, all bets are off on
            # what the amount represents (see unlock_event).
            amount = prorated_amount
        if not created_at:
            created_at = datetime.datetime.utcnow().replace(tzinfo=utc)
        return Transaction(
            created_at=created_at,
            descr=descr,
            orig_amount=nb_periods,
            orig_units=self.plan.id,
            orig_account=Transaction.INCOME,
            orig_organization=self.plan.organization,
            dest_amount=amount,
            dest_account=Transaction.PAYABLE,
            dest_organization=self.organization,
            event_id=self.id)


class TransactionManager(models.Manager):

    def by_charge(self, charge):
        #pylint: disable=no-self-use
        return charge.invoiced_items.all()

    def by_subsciptions(self, subscriptions, at_time=None):
        """
        Returns a ``QuerySet`` of all transactions related to a set
        of subscriptions.
        """
        queryset = self.filter(
            models.Q(dest_account=Transaction.PAYABLE)
            | models.Q(dest_account=Transaction.REDEEM),
            event_id__in=subscriptions)
        if at_time:
            queryset = queryset.filter(created_at=at_time)
        return queryset.order_by('created_at')

    def create_credit(self, customer, amount):
        credit = self.create(
            orig_organization=Organization.objects.get_site_owner(),
            dest_organization=customer,
            orig_account='Incentive', dest_account='Balance',
            amount=amount,
            descr='Credit for creating an organization')
        credit.save()
        return credit

    def execute_order(self, invoiced_items):
        """
        Save invoiced_items, a set of ``Transaction`` and update when
        each associated ``Subscription`` ends.

        This method returns the invoiced items as a QuerySet.

        Constraints: All invoiced_items to same customer
        """
        invoiced_items_ids = []
        for invoiced_item in invoiced_items:
            pay_now = True
            subscription = Subscription.objects.get(pk=invoiced_item.event_id)
            if invoiced_item.orig_units != 'usd':
                # XXX need to reverse and maybe introduce sepical *period* unit
                subscription.ends_at = subscription.plan.end_of_period(
                    subscription.ends_at, invoiced_item.orig_amount)
            subscription.save()
            if (subscription.plan.unlock_event
                and invoiced_item.dest_amount == 0):
                # We are dealing with access now, pay later, orders.
                invoiced_item.dest_amount = subscription.plan.period_amount
                pay_now = False
            invoiced_item.orig_amount = invoiced_item.dest_amount
            invoiced_item.orig_units = invoiced_item.dest_units
            invoiced_item.save()
            if pay_now:
                invoiced_items_ids += [invoiced_item.id]
        return self.filter(id__in=invoiced_items_ids)

    def get_organization_balance(self, organization, account=None):
        """
        Returns the balance on an organization's account
        (by default: ``Payable``).
        """
        if not account:
            account = Transaction.PAYABLE
        dest_amount = sum_dest_amount(self.filter(
            dest_organization=organization,
            dest_account=account))
        orig_amount = sum_orig_amount(self.filter(
            orig_organization=organization,
            orig_account=account))
        return dest_amount - orig_amount

    def get_subscription_balance(self, subscription):
        """
        Returns the ``Payable`` balance on a subscription.

        The balance on a subscription is used to determine when
        a subscription is locked (balance due) or unlocked (no balance).
        """
        dest_amount = sum_dest_amount(self.filter(
            dest_organization=subscription.organization,
            dest_account=Transaction.PAYABLE,
            event_id=subscription.id))
        orig_amount = sum_orig_amount(self.filter(
            orig_organization=subscription.organization,
            orig_account=Transaction.PAYABLE,
            event_id=subscription.id))
        return dest_amount - orig_amount

    def get_subscription_payable(self, subscription, created_at=None):
        """
        Returns a ``Transaction`` for the subscription balance.
        """
        if not created_at:
            created_at = datetime.datetime.utcnow().replace(tzinfo=utc)
        balance = self.get_subscription_balance(subscription)
        return Transaction(
            created_at=created_at,
            descr=DESCRIBE_BALANCE % {'plan': subscription.plan},
            orig_amount=balance,
            orig_account=Transaction.PAYABLE,
            orig_organization=subscription.organization,
            dest_amount=balance,
            dest_account=Transaction.PAYABLE,
            dest_organization=subscription.organization)

    def get_subscription_later(self, subscription, created_at=None):
        """
        Returns a ``Transaction`` for the subscription balance to be paid later.
        """
        if not created_at:
            created_at = datetime.datetime.utcnow().replace(tzinfo=utc)
        balance = self.get_subscription_balance(subscription)
        return Transaction(
            created_at=created_at,
            descr=('Pay balance of %s on %s later'
                   % (as_money(balance), subscription.plan)),
            orig_amount=balance,
            orig_account=Transaction.PAYABLE,
            orig_organization=subscription.organization,
            dest_amount=0,
            dest_account=Transaction.PAYABLE,
            dest_organization=subscription.organization)


class Transaction(models.Model):
    '''The Transaction table stores entries in the double-entry bookkeeping
    ledger.

    'Invoiced' comes from the service. We use for acrual tax reporting.
    We have one 'invoiced' for each job? => easy to reconciliate.

    'Balance' is amount due.

    use 'ledger register' for tax acrual tax reporting.
    '''
    FUNDS = 'Funds'
    INCOME = 'Income'
    PAYABLE = 'Payable'
    EXPENSES = 'Expenses'

    CHARGEBACK = 'Chargeback'
    REDEEM = 'Redeem'
    REFUND = 'Refund'
    WRITEOFF = 'Writeoff'

    objects = TransactionManager()

    # Implementation Note:
    # An exact created_at is to important to let auto_now_add mess with it.
    created_at = models.DateTimeField()

    orig_account = models.CharField(max_length=30, default="unknown")
    orig_organization = models.ForeignKey(Organization,
        related_name="outgoing")
    orig_amount = models.IntegerField(default=0,
        help_text=_('amount withdrawn from origin in origin units'))
    orig_units = models.CharField(max_length=3, default="usd",
        help_text=_('Measure of units on origin account'))

    dest_account = models.CharField(max_length=30, default="unknown")
    dest_organization = models.ForeignKey(Organization,
        related_name="incoming")
    dest_amount = models.IntegerField(default=0,
        help_text=_('amount deposited into destination in destination units'))
    dest_units = models.CharField(max_length=3, default="usd",
        help_text=_('Measure of units on destination account'))

    # Optional
    descr = models.TextField(default="N/A")
    event_id = models.SlugField(null=True, help_text=
        _('Event at the origin of this transaction (ex. job, charge, etc.)'))

    def __unicode__(self):
        return unicode(self.id)


class NewVisitors(models.Model):
    """
    New Visitors metrics populated by reading the web server logs.
    """
    date = models.DateField(unique=True)
    visitors_number = models.IntegerField(default=0)

    def __unicode__(self):
        return unicode(self.id)


def sum_dest_amount(transactions):
    """
    Return the sum of the amount in the *transactions* set.
    """
    amount = 0
    if isinstance(transactions, QuerySet):
        amount = transactions.aggregate(Sum('dest_amount'))['dest_amount__sum']
        if amount is None:
            amount = 0
    else:
        for item in transactions:
            amount += item.dest_amount
    return amount

def sum_orig_amount(transactions):
    """
    Return the sum of the amount in the *transactions* set.
    """
    amount = 0
    if isinstance(transactions, QuerySet):
        amount = transactions.aggregate(Sum('orig_amount'))['orig_amount__sum']
        if amount is None:
            amount = 0
    else:
        for item in transactions:
            amount += item.dest_amount
    return amount
