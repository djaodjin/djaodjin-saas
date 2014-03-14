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

from django.db import models, transaction
from django.db.models import Sum
from django.utils.timezone import utc
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _
from django.utils.decorators import method_decorator
from stripe.error import InvalidRequestError

from saas import settings
from saas import get_manager_relation_model, get_contributor_relation_model

LOGGER = logging.getLogger(__name__)


class OrganizationManager(models.Manager):

    def add_contributor(self, organization, user):
        """
        Add user as a contributor to organization.
        """
        relation = get_contributor_relation_model()(
            organization=organization, user=user)
        relation.save()

    def add_manager(self, organization, user):
        """
        Add user as a manager to organization.
        """
        relation = get_manager_relation_model()(
            organization=organization, user=user)
        relation.save()

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
                               slug=name,
                               billing_start=billing_start)
        # XXX We give each customer a certain amount of free time
        # to play with it.
        # Amount is in cents.
        credit = Transaction.objects.create_credit(
            customer, settings.CREDIT_ON_CREATE)
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
            LOGGER.info('Created processor_id #%s for %s',
                        customer.processor_id, customer)
        else:
            backend.update_card(customer, card)

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

    def get_site(self):
        return Site.objects.get(pk=settings.SITE_ID)

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


class Organization_Managers(models.Model):
    organization = models.ForeignKey('Organization')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='user_id')

    class Meta:
        unique_together = ('organization', 'user')


class Organization_Contributors(models.Model):
    organization = models.ForeignKey('Organization')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='user_id')

    class Meta:
        unique_together = ('organization', 'user')


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

    def __unicode__(self):
        return unicode(self.slug)


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


class CartItemManager(models.Manager):

    def get_cart(self, user):
        return self.filter(user=user, recorded=False)

    def as_transaction(self, subscription, customer, amount,
                       start_time=None, descr=None):
        if not start_time:
            start_time = datetime.datetime.utcnow().replace(tzinfo=utc)
        return Transaction(
            created_at=start_time,
            amount=amount,
            descr=descr,
            orig_account=Transaction.INCOME,
            dest_account=Transaction.PAYABLE,
            orig_organization=subscription.plan.organization,
            dest_organization=customer)

    def get_invoicables_for(self, subscription, customer,
                            start_time=None, prorate_to=None):
        if not start_time:
            start_time = datetime.datetime.utcnow().replace(tzinfo=utc)
        invoicables = []
        plan = subscription.plan
        if plan.setup_amount:
            # One time setup fee always charged in full.
            if plan.period_amount:
                descr = "%s (one-time setup)" % plan.get_title()
            else:
                descr = plan.get_title()
            invoicables += [self.as_transaction(subscription, customer,
                plan.setup_amount, start_time, descr)]
        if prorate_to:
            prorated_amount = plan.prorate_period(start_time, prorate_to)
            descr = "%s (pro-rated first period)" % plan.get_title()
        else:
            prorated_amount = plan.period_amount
            descr = "%s (first period)" % plan.get_title()
        if prorated_amount:
            # The prorated amount might still be zero in which case we don't
            # want to add it to the invoice.
            invoicables += [self.as_transaction(subscription, customer,
                prorated_amount, start_time, descr)]
        return invoicables

    def get_invoicables(self, customer, user, coupons,
                        start_time=None, prorate_to_billing=False):
        """
        Returns a list of invoicable items (amount, description)
        from the items in a user/customer cart. Schema:
        invoicable_items = [
            { "subscription": Subscription,
              "lines": [{
              }, ...],
            }, ...]
        """
        invoicables = []
        if not start_time:
            start_time = datetime.datetime.utcnow().replace(tzinfo=utc)
        prorate_to = None
        if prorate_to_billing:
            # XXX First we add enough periods to get the next billing date later
            # than start_time but no more than one period in the future.
            prorate_to = customer.billing_start
        invoiced_items = []
        for cart_item in self.get_cart(user=user):
            try:
                subscription = Subscription.objects.get(
                    organization=customer, plan=cart_item.plan)
            except Subscription.DoesNotExist:
                subscription = Subscription(
                    organization=customer, plan=cart_item.plan)
            lines = self.get_invoicables_for(
                    subscription, customer, start_time, prorate_to)
            item_amount = 0
            for line in lines:
                item_amount = item_amount + line.amount
            for coupon in coupons:
                coupon_amount = item_amount * coupon.percentage / 100
                lines += [Transaction(
                        created_at=start_time,
                        amount=coupon_amount,
                        descr='redeem coupon #%s' % coupon.code,
                        orig_account=Transaction.PAYABLE,
                        dest_account=Transaction.REDEEM,
                        orig_organization=customer,
                        dest_organization=subscription.plan.organization)]
            invoiced_items += [{'subscription': subscription, "lines": lines}]
        return invoiced_items

    @method_decorator(transaction.atomic)
    def checkout(self, customer, user, coupons, start_time=None):
        """
        Creates transactions based on a set of items in a cart.
        """
        subscriptions = []
        if not start_time:
            start_time = datetime.datetime.utcnow().replace(tzinfo=utc)
        for invoicable in self.get_invoicables(
                customer, user, coupons, start_time=start_time):
            subscription = invoicable['subscription']
            if not subscription.id:
                subscription.save()
                subscriptions += [subscription]
                for transaction in invoicable['lines']:
                    # We can't set the event_id until the subscription is saved
                    # in the database.
                    transaction.event_id = subscription.id
                    transaction.save()
            cart_items = self.filter(
                user=user, plan=subscription.plan, recorded=False)
            if cart_items.exists():
                cart_item = cart_items.get()
                cart_item.recorded = True
                cart_item.save()
        # XXX Filters all subscriptions which are due at the time of checkout.
        return Transaction.objects.none()


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


class ChargeManager(models.Manager):

    def charge_card(self, customer, transactions, description=None,
                    user=None, token=None, remember_card=True):
        """
        Create a charge on a customer card.
        """
        # Be careful, stripe will not processed charges less than 50 cents.
        import saas.backends as backend # Avoid import loop
        amount = transactions.aggregate(Sum('amount')).get('amount__sum', 0)
        if amount is None:
            amount = 0
        descr = '%s subscriptions through %s' % (
            customer.full_name,
            Organization.objects.get_site_owner().full_name)
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
            charge.invoiced_items.add(*transactions)
            charge.save()
            LOGGER.info('Created charge #%s of %d cents to %s',
                        charge.id, charge.amount, customer)
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

    @property
    def is_disputed(self):
        return self.state == self.DISPUTED

    @property
    def is_failed(self):
        return self.state == self.FAILED

    @property
    def is_paid(self):
        return self.state == self.DONE


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
    # end game
    length = models.IntegerField(null=True, blank=True,
        help_text=_('Number of intervals the plan before the plan ends.'))
    # Pb with next : maybe create an other model for it
    next_plan = models.ForeignKey("Plan", null=True)

    class Meta:
        unique_together = ('slug', 'organization')

    def __unicode__(self):
        return unicode(self.slug)

    def get_title(self):
        """
        Returns a printable human-readable title for the plan.
        """
        if self.title:
            return self.title
        return self.slug

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


class Subscription(models.Model):
    """
    Subscriptions of an Organization to a Plan
    """
    created_at = models.DateTimeField(auto_now_add=True)
    organization = models.ForeignKey('Organization')
    plan = models.ForeignKey('Plan')

    class Meta:
        unique_together = ('organization', 'plan')


class TransactionManager(models.Manager):

    def by_charge(self, charge):
        return charge.invoiced_items.all()

    def by_subsciptions(self, subscriptions, at_time):
        return self.filter(
            models.Q(dest_account=Transaction.PAYABLE)
            | models.Q(dest_account=Transaction.REDEEM),
            event_id__in=subscriptions,
            created_at=at_time).order('created_at')

    def create_credit(self, customer, amount):
        credit = self.create(
            orig_organization=Organization.objects.get_site_owner(),
            dest_organization=customer,
            orig_account='Incentive', dest_account='Balance',
            amount=amount,
            descr='Credit for creating an organization')
        credit.save()
        return credit

    def get_balance(self, organization,
        account='Payable'): # ``Transaction`` is not defined at this point.
        """
        Returns payable balance for an organization
        """
        amount = self.filter(dest_organization=organization,
            dest_account=Transaction.PAYABLE).aggregate(
            Sum('amount'))['amount__sum']
        if amount is None:
            due_amount = 0
        else:
            due_amount = amount
        amount = self.filter(orig_organization=organization,
            orig_account=Transaction.PAYABLE).aggregate(
            Sum('amount'))['amount__sum']
        if amount is None:
            paid_amount = 0
        else:
            paid_amount = amount
        return due_amount - paid_amount

    def get_invoicables(self, subscription):
        """
        Returns transactions which have not been charged to a customer yet.

        invoicable_items = [
            { "subscription": Subscription,
              "lines": [{
              }, ...],
            }, ...]
        """
        customer = subscription.organization
        # All Transactions related to this subscription since the last payment.
        last_charge = Charge.objects.last_charge(subscription)
        if last_charge:
            queryset = self.filter(
                models.Q(dest_account=Transaction.PAYABLE)
                | models.Q(dest_account=Transaction.REDEEM),
                event_id=subscription.id,
                created_at__gt=last_charge.created_at).order(
                    'created_at')
        else:
            queryset = self.filter(
                models.Q(dest_account=Transaction.PAYABLE)
                | models.Q(dest_account=Transaction.REDEEM),
                event_id=subscription.id).order_by('created_at')
        invoiced_amount = 0
        amount = queryset.filter(dest_account=Transaction.PAYABLE).aggregate(
            Sum('amount'))['amount__sum']
        if amount is not None:
            invoiced_amount += amount
        amount = queryset.filter(dest_account=Transaction.REDEEM).aggregate(
            Sum('amount'))['amount__sum']
        if amount is not None:
            invoiced_amount -= amount
        invoiced_subscription = {
            'subscription': subscription, 'lines': list(queryset)}
        balance = self.get_balance(customer) - invoiced_amount
        if balance != 0:
            return [{'subscription': None,
                       'lines': [Transaction(
                amount=balance,
                descr='balance for %s' % subscription.organization,
                orig_account=Transaction.INCOME,
                dest_account=Transaction.PAYABLE,
                orig_organization=subscription.plan.organization,
                dest_organization=customer)]},
                    invoiced_subscription]
        return [invoiced_subscription]

    def invoice(self, customer, amount,
                description=None, event_id=None, created_at=None):
        if not created_at:
            created_at = datetime.datetime.utcnow().replace(tzinfo=utc)
        usage = self.create(
            orig_organization=customer, dest_organization=customer,
            orig_account="Usage", dest_account="Balance",
            amount=amount,
            descr=description,
            event_id=event_id,
            created_at=created_at)

    def refund(self, customer, amount, description=None, event_id=None):
        usage = self.create(
            orig_organization=Organization.objects.get_site_owner(),
            orig_account=Transaction.ASSETS,
            dest_organization=Organization.objects.get_site_owner(),
            dest_account=Transaction.REFUND,
            amount=amount,
            descr=description,
            event_id=event_id)
        usage = self.create(
            orig_organization=Organization.objects.get_site_owner(),
            orig_account=Transaction.REFUND,
            dest_organization=customer,
            dest_account='Balance',
            amount=amount,
            descr=description,
            event_id=event_id)

    def pay_balance(self, customer, amount, description=None, event_id=None):
        payment = self.create(
            orig_organization=customer,
            dest_organization=Organization.objects.get_site_owner(),
            orig_account=Transaction.PAYABLE, dest_account=Transaction.ASSETS,
            amount=amount,
            descr=description,
            event_id=event_id)
        payment.save()
        return payment


class Transaction(models.Model):
    '''The Transaction table stores entries in the double-entry bookkeeping
    ledger.

    'Invoiced' comes from the service. We use for acrual tax reporting.
    We have one 'invoiced' for each job? => easy to reconciliate.

    'Balance' is amount due.

    use 'ledger register' for tax acrual tax reporting.
    '''
    ASSETS = 'Assets'
    CHARGEBACK = 'Chargeback'
    INCOME = 'Income'
    PAYABLE = 'Payable'
    REDEEM = 'Redeem'
    REFUND = 'Refund'
    WRITEOFF = 'Writeoff'

    objects = TransactionManager()

    created_at = models.DateTimeField(auto_now_add=True)
    # Amount in cents
    amount = models.IntegerField(default=0)
    orig_account = models.CharField(max_length=30, default="unknown")
    dest_account = models.CharField(max_length=30, default="unknown")
    orig_organization = models.ForeignKey(Organization,
                                          related_name="outgoing")
    dest_organization = models.ForeignKey(Organization,
                                          related_name="incoming")
    # Optional
    descr = models.TextField(default="N/A")
    event_id = models.SlugField(null=True, help_text=
        _('Event at the origin of this transaction (ex. job, charge, etc.)'))

    @property
    def is_payable(self):
        return self.dest_account == self.PAYABLE


class NewVisitors(models.Model):
    """
    New Visitors metrics populated by reading the web server logs.
    """
    date = models.DateField(unique=True)
    visitors_number = models.IntegerField(default=0)
