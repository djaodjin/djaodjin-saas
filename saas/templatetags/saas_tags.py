# Copyright (c) 2014, DjaoDjin inc.
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

import re
from datetime import datetime, timedelta

from django import template
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe

from saas.humanize import (DESCRIBE_BALANCE, DESCRIBE_BUY_PERIODS,
    DESCRIBE_UNLOCK_NOW, DESCRIBE_UNLOCK_LATER)
from saas.models import Organization, Subscription, Transaction
from saas.views.auth import valid_manager_for_organization

register = template.Library()


@register.filter()
def is_debit(transaction, organization):
    """
    True if the transaction can be tagged as a debit. That is
    it is either payable by the organization or the transaction
    moves from a Funds account to the organization's Expenses account.
    """
    return ((transaction.dest_organization == organization           # customer
             and transaction.dest_account == Transaction.EXPENSES)
            or (transaction.orig_organization == organization        # provider
             and transaction.orig_account == Transaction.FUNDS))


@register.filter()
def is_incomplete_month(date):
    return ((isinstance(date, basestring) and not date.endswith('01'))
        or (isinstance(date, datetime) and date.day != 1))


@register.filter()
def monthly_caption(last_date):
    """returns a formatted caption describing the period whose end
    date is *last_date*."""
    if last_date.day == 1:
        prev = last_date - timedelta(days=2) # more than one day to make sure
        return datetime.strftime(prev, "%b'%y")
    else:
        return datetime.strftime(last_date, "%b'%y") + "*"


@register.filter()
def person(user):
    """
    Returns the person ``Organization`` associated to the user or None
    in none can be reliably found.
    """
    queryset = Organization.objects.filter(slug=user.username)
    if queryset.exists():
        return queryset.get()
    return None


@register.filter()
def products(subscriptions):
    """
    Returns a list of distinct providers (i.e. ``Organization``) from
    the plans the *organization* is subscribed to.
    """
    if subscriptions:
        # We don't use QuerySet.distinct('organization') because SQLite
        # does not support DISTINCT ON queries.
        return subscriptions.values(
            'organization__slug', 'organization__full_name').distinct()
    return []


@register.filter()
def top_managed_organizations(user):
    """
    Returns a queryset of the 8 most important organizations the user
    is a manager for.
    """
    return user.manages.all()[:8]


@register.filter()
def more_managed_organizations(user):
    """
    Returns True if the user manages more than 8 organizations.
    """
    return user.manages.count() >= 8


@register.filter
def is_manager(request, organization):
    try:
        valid_manager_for_organization(request.user, organization)
    except PermissionDenied:
        return False
    return True


@register.filter
def is_site_owner(organization):
    return organization.pk == settings.SITE_ID


@register.filter
def active_with_provider(organization, provider):
    """
    Returns a list of active subscriptions for organization for which provider
    is the owner of the plan.
    """
    return Subscription.objects.active_with_provider(organization, provider)


@register.filter(needs_autoescape=False)
def describe(transaction):
    provider = transaction.orig_organization
    subscriber = transaction.dest_organization
    look = re.match(DESCRIBE_BUY_PERIODS % {
        'plan': r'(?P<plan>\S+)', 'ends_at': r'.*', 'humanized_periods': r'.*'},
        transaction.descr)
    if not look:
        look = re.match(DESCRIBE_UNLOCK_NOW % {
            'plan': r'(?P<plan>\S+)', 'unlock_event': r'.*'},
            transaction.descr)
    if not look:
        look = re.match(DESCRIBE_UNLOCK_LATER % {
            'plan': r'(?P<plan>\S+)', 'unlock_event': r'.*',
            'amount': r'.*'}, transaction.descr)
    if not look:
        look = re.match(DESCRIBE_BALANCE % {
            'plan': r'(?P<plan>\S+)'}, transaction.descr)
    if not look:
        # DESCRIBE_CHARGED_CARD, DESCRIBE_CHARGED_CARD_PROCESSOR
        # and DESCRIBE_CHARGED_CARD_PROVIDER.
        # are specially crafted to start with "Charge ..."
        look = re.match(r'Charge (?P<charge>\S+)', transaction.descr)
        if look:
            link = '<a href="%s">%s</a>' % (reverse('saas_charge_receipt',
                args=(subscriber, look.group('charge'),)), look.group('charge'))
            return mark_safe(
                transaction.descr.replace(look.group('charge'), link))
        return transaction.descr

    plan_link = ('<a href="/%s/app/%s/%s/">%s</a>' %
        (provider, subscriber, look.group('plan'), look.group('plan')))
    return mark_safe(
            transaction.descr.replace(look.group('plan'), plan_link))


@register.filter(needs_autoescape=False)
def refund_enable(transaction, user):
    """
    Returns True if *user* is able to trigger a refund on *transaction*.
    """
    subscription = Subscription.objects.filter(pk=transaction.event_id).first()
    if subscription:
        try:
            valid_manager_for_organization(user, subscription.plan.organization)
            return True
        except PermissionDenied:
            pass
    return False


