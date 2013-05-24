# Copyright (c) 2013, Fortylines LLC
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

import datetime, logging

from django.db import models

from saas.settings import SITE_ID, CREDIT_ON_CREATE

LOGGER = logging.getLogger(__name__)


class OrganizationManager(models.Manager):

    def create_organization(self, name, creation_time):
        from saas.models import Transaction # avoid import loop
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
        from saas.models import Organization
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
        else:
            backend.update_card(customer, card)

    def get_site_owner(self):
        return self.get(pk=SITE_ID)


class SignatureManager(models.Manager):

    def create_signature(self, agreement, user):
        from saas.models import Agreement, Signature # avoid import loop
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
        from saas.models import Agreement, Signature # avoid import loop
        if isinstance(agreement, basestring):
            agreement = Agreement.objects.get(slug=agreement)
        try:
            sig = self.get(agreement=agreement, user=user)
            if sig.last_signed < agreement.modified:
                return False
        except Signature.DoesNotExist:
            return False
        return True


class TransactionManager(models.Manager):

    def create_credit(self, customer, amount):
        from saas.models import Organization # avoid import loop
        credit = self.create(
            orig_organization=Organization.objects.get_site_owner(),
            dest_organization=customer,
            orig_account='Incentive', dest_account='Balance',
            amount=amount,
            descr='Credit for creating an organization')
        credit.save()
        return credit

    def invoice(self, customer, amount, description=None, event_id=None):
        usage = Transaction.objects.create(
            orig_organization=customer, dest_organization=customer,
            orig_account="Usage", dest_account="Balance",
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


class ChargeManager(models.Manager):

    def charge_card(self, customer, amount, user=None):
        """Create a charge on a customer card."""
        # Be careful, stripe will not processed charges less than 50 cents.
        import saas.backends as backend # Avoid import loop
        descr = 'fortylines usage for %s' % customer.name
        if user:
            descr += ' (%s)' % user.username
        processor_charge_id, created_at = backend.create_charge(
            customer, amount, descr)
        # Create record of the charge in our database
        charge = self.create(pk=processor_charge_id, amount=amount,
                             created_at=created_at, customer=customer)
        if charge:
            LOGGER.info('charge: %s', charge)
        return charge

