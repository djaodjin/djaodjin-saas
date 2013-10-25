# Copyright (c) 2013, The DjaoDjin Team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
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

from django.db import models
from django.utils.timezone import utc
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from durationfield.db.models.fields.duration import DurationField

from saas.settings import (MANAGER_RELATION, CONTRIBUTOR_RELATION,
                           SITE_ID, CREDIT_ON_CREATE)

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
                               name=name,
                               billing_start=billing_start)
        # XXX We give each customer a certain amount of free time
        # to play with it.
        # Amount is in cents.
        credit = Transaction.objects.create_credit(customer, CREDIT_ON_CREATE)
        return customer

    def associate_processor(self, customer, card=None):
        import saas.backends as backend # avoid import loop
        if not isinstance(customer, Organization):
            if isinstance(customer, basestring):
                customer = self.get(name=customer)
            else:
                customer = self.get(pk=customer)
        if not customer.processor_id:
            # We don't have a processor_id yet for this customer,
            # so let's create one.
            customer.processor_id = backend.create_customer(
                customer.name, card)
            customer.save()
            LOGGER.info('Created processor_id #%s', customer.processor_id)
        else:
            backend.update_card(customer, card)

    def get_site_owner(self):
        return self.get(pk=SITE_ID)


class Organization(models.Model):
    """
    The Organization table stores information about who gets
    charged (and who gets paid) for using the service. Users can
    have one of two relationships with an Organization. They can
    either be managers (all permissions) or contributors (use permissions).
    """

    objects = OrganizationManager()
    name = models.SlugField(unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    # contact by e-mail
    email = models.EmailField()
    # contact by phone
    phone = models.CharField(max_length=50)
    # contact by physical mail
    street_address = models.CharField(max_length=150)
    locality = models.CharField(max_length=50)
    region = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=50)
    country_name = models.CharField(max_length=75)

    belongs = models.ForeignKey('Organization', null=True)
    if MANAGER_RELATION:
        managers = models.ManyToManyField(User, related_name='manages',
                                          through=MANAGER_RELATION)
    else:
        managers = models.ManyToManyField(User, related_name='manages')

    if CONTRIBUTOR_RELATION:
        contributors = models.ManyToManyField(User, related_name='contributes',
                                              through=CONTRIBUTOR_RELATION)
    else:
        contributors = models.ManyToManyField(User, related_name='contributes')

    # Payment Processing
    # We could support multiple payment processors at the same time by
    # by having a relation to a separate table. For simplicity we only
    # allow on processor per organization at a time.
    subscriptions = models.ManyToManyField('Plan', related_name='subscribes')
    billing_start = models.DateField(null=True, auto_now_add=True)
    processor = models.CharField(null=True, max_length=20)
    processor_id = models.CharField(null=True,
        blank=True, max_length=20)

    def __unicode__(self):
        return unicode(self.name)


class Agreement(models.Model):
    slug = models.SlugField()
    title =  models.CharField(max_length=150, unique=True)
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
    user = models.ForeignKey(User)
    class Meta:
        unique_together = ('agreement', 'user')


class CartItemManager(models.Manager):

    def get_cart(self, customer, user):
        return self.filter(user=user, customer=customer, recorded=False)

    def get_invoicables_for(self, item, start_date=None):
        invoicables = []
        if not start_date:
            start_date = datetime.datetime.utcnow().replace(tzinfo=utc)
        prorated_amount = item.prorated_first_month(start_date)
        if item.subscription.setup_amount:
            # One time setup fee always charged in full.
            invoicables += [{
                    "amount": item.subscription.setup_amount,
                    "description": ("one-time setup for %s"
                                    % item.subscription.slug)}]
        if prorated_amount:
            invoicables += [{
                    "amount": prorated_amount,
                    "description": ("pro-rated first month for %s"
                                    % item.subscription.slug)}]
        return invoicables


    def get_invoicables(self, customer, user, start_date=None):
        """
        Returns a list of invoicable items (amount, description)
        from the items in a user/customer cart.
        """
        invoicables = []
        if not start_date:
            start_date = datetime.datetime.utcnow().replace(tzinfo=utc)
        items = self.get_cart(customer=customer, user=user)
        for item in items:
            invoicables += self.get_invoicables_for(item, start_date)
        return invoicables


class CartItem(models.Model):
    """
    Items which are been ordered. These represent an active cart.
    """
    objects = CartItemManager()

    user = models.ForeignKey(User)
    customer = models.ForeignKey(Organization)
    created_at = models.DateTimeField(auto_now_add=True)
    subscription = models.ForeignKey('Plan')
    recorded = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'customer')

    def prorated_first_month(self, start_date):
        """Subscriptions are pro-rated based on the billing cycle.
        If no billing cycle exists for this customer, one is created.
        """
        if self.customer.billing_start:
            since_billing_start = (start_date.date()
                - self.customer.billing_start).total_seconds()
            interval_length = self.subscription.interval.total_seconds()
            return int(self.subscription.amount
                       * (since_billing_start % interval_length)
                       / interval_length)
        else:
            return self.subscription.amount


class ChargeManager(models.Manager):

    def charge_card(self, customer, amount, description=None,
                    user=None, token=None, remember_card=True):
        """
        Create a charge on a customer card.
        """
        # Be careful, stripe will not processed charges less than 50 cents.
        import saas.backends as backend # Avoid import loop
        descr = '%s subscription to %s' % (
            customer.name,
            Organization.objects.get_site_owner().name)
        if user:
            descr += ' (%s)' % user.username
        if token:
            if remember_card:
                Organization.objects.associate_processor(customer, card=token)
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
        charge = self.create(processor_id=processor_charge_id, amount=amount,
                             created_at=created_at, customer=customer,
                             description=descr, last4=last4, exp_date=exp_date)
        if charge:
            LOGGER.info('Created charge #%s', charge.id)
        return charge


class Charge(models.Model):
    """
    Keep track of charges that have been emitted by the app.
    We save the last4 and expiration date so we are able to present
    a receipt.
    """
    CREATED  = 0
    DONE     = 1
    FAILED   = 2
    DISPUTED = 3
    CHARGE_STATES = {
        (CREATED, 'created'),
        (DONE, 'done'),
        (FAILED, 'failed'),
        (DISPUTED, 'disputed')
    }

    objects = ChargeManager()

    created_at = models.DateTimeField(auto_now_add=True)
    # Amount in cents
    amount = models.IntegerField(default=0)
    customer = models.ForeignKey(Organization)
    description = models.TextField()
    last4 = models.IntegerField()
    exp_date = models.DateField()
    processor = models.SlugField()
    processor_id = models.SlugField(db_index=True)
    state = models.SmallIntegerField(choices=CHARGE_STATES, default=CREATED)


class Coupon(models.Model):
    """
    Coupons are used on invoiced to give a rebate to a customer.
    """
    user = models.ForeignKey(User, null=True)
    customer = models.ForeignKey(Organization, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    code = models.SlugField(primary_key=True, db_index=True)
    redeemed = models.BooleanField(default=False)


class Plan(models.Model):
    """
    Recurring billing plan
    """
    slug = models.SlugField()
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True) # we use created_at by convention in other models.
    discontinued_at = models.DateTimeField(null=True,blank=True)
    organization = models.ForeignKey(Organization)
    # initial
    setup_amount = models.IntegerField()
    # recurring
    amount = models.IntegerField()
    interval = DurationField(default=datetime.timedelta(days=30))
    # end game
    length = models.IntegerField(null=True,blank=True) # in intervals/periods
    # Pb with next : maybe create an other model for it
    next_plan = models.ForeignKey("Plan", null=True)

    def __unicode__(self):
        return unicode(self.slug)


class TransactionManager(models.Manager):

    def create_credit(self, customer, amount):
        credit = self.create(
            orig_organization=Organization.objects.get_site_owner(),
            dest_organization=customer,
            orig_account='Incentive', dest_account='Balance',
            amount=amount,
            descr='Credit for creating an organization')
        credit.save()
        return credit

    def invoice(self, customer, amount,
                description=None, event_id=None, created_at=None):
        if not created_at:
            at = start_date = datetime.datetime.utcnow().replace(tzinfo=utc)
        usage = self.create(
            orig_organization=customer, dest_organization=customer,
            orig_account="Usage", dest_account="Balance",
            amount=amount,
            descr=description,
            event_id=event_id,
            created_at=created_at)

    def redeem_coupon(self, amount, coupon):
        if amount:
            self.create(
                orig_organization=Organization.objects.get_site_owner(),
                orig_account='Redeem',
                dest_organization=coupon.customer,
                dest_account='Balance',
                amount=amount,
                descr='redeem coupon #%s' % coupon.code)
            coupon.redeemed = True

    def refund(self, customer, amount, description=None, event_id=None):
        usage = self.create(
            orig_organization=Organization.objects.get_site_owner(),
            orig_account='Assets',
            dest_organization=Organization.objects.get_site_owner(),
            dest_account='Refund',
            amount=amount,
            descr=description,
            event_id=event_id)
        usage = self.create(
            orig_organization=Organization.objects.get_site_owner(),
            orig_account='Refund',
            dest_organization=customer,
            dest_account='Balance',
            amount=amount,
            descr=description,
            event_id=event_id)

    def pay_balance(self, customer, amount, description=None, event_id=None):
        payment = self.create(
            orig_organization=customer,
            dest_organization=Organization.objects.get_site_owner(),
            orig_account='Balance', dest_account='Assets',
            amount=amount,
            descr=description,
            event_id=event_id)
        payment.save()
        return payment

    def subscribe_to(self, cart, start_date=None):
        """
        Creates transactions based on a set of items in a cart.
        """
        if not start_date:
            start_date = datetime.datetime.utcnow().replace(tzinfo=utc)
        for item in cart:
            invoicables = CartItem.objects.get_invoicables_for(item, start_date)
            for invoicable in invoicables:
                self.invoice(item.customer, invoicable["amount"],
                    description=invoicable["description"],
                    created_at=start_date)
            item.customer.subscriptions.add(item.subscription)
            item.recorded = True
            item.save()


class Transaction(models.Model):
    '''The Transaction table stores entries in the double-entry bookkeeping
    ledger.

    'Invoiced' comes from the service. We use for acrual tax reporting.
    We have one 'invoiced' for each job? => easy to reconciliate.

    'Balance' is amount due.

    use 'ledger register' for tax acrual tax reporting.
    '''

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


class NewVisitors(models.Model):
    """
    New Visitors metrics populated by reading the web server logs.
    """
    date = models.DateField(unique=True)
    visitors_number = models.IntegerField(default = 0)
