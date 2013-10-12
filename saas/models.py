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

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from durationfield.db.models.fields.duration import DurationField

from saas.settings import MANAGER_RELATION, CONTRIBUTOR_RELATION
from saas.managers import (
    OrganizationManager,
    SignatureManager,
    TransactionManager,
    ChargeManager)


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


class Signature(models.Model):
    objects = SignatureManager()

    last_signed = models.DateTimeField(auto_now_add=True)
    agreement = models.ForeignKey(Agreement)
    user = models.ForeignKey(User)
    class Meta:
        unique_together = ('agreement', 'user')


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


class Charge(models.Model):
    '''Keep track of charges that have been emitted by the app.'''
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
    processor = models.SlugField()
    processor_id = models.SlugField(primary_key=True, db_index=True)
    state = models.SmallIntegerField(choices=CHARGE_STATES, default=CREATED)


class NewVisitors(models.Model):
    """
    New Visitors metrics populated by reading the web server logs.
    """
    date = models.DateField(unique=True)
    visitors_number = models.IntegerField(default = 0)


class Plan(models.Model):
    """
    Recurring billing plan
    """
    slug = models.SlugField()
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True) # we use created_at by convention in other models.
    discontinued_at = models.DateTimeField(null=True,blank=True)
    customer = models.ForeignKey(Organization)
    # initial
    setup_amount = models.IntegerField()
    # recurring
    amount = models.IntegerField()
    interval = DurationField(null=True)  # if possible
    # end game
    length = models.IntegerField(null=True,blank=True) # in intervals/periods
    # Pb with next : maybe create an other model for it
    next_plan = models.ForeignKey("Plan", null=True)

    def __unicode__(self):
        return unicode(self.slug)

