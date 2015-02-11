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

from datetime import datetime, timedelta

import markdown
from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.utils.timezone import utc

from saas import settings
from saas.compat import User
from saas.humanize import as_html_description
from saas.models import (Organization, Subscription, Transaction,
    get_current_provider)
from saas.decorators import pass_direct, _valid_manager
from saas.utils import product_url as utils_product_url

register = template.Library()


@register.filter()
def is_current_provider(organization):
    # XXX Use slug because both organizations might come from a different db.
    return organization.slug == get_current_provider().slug


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


@register.filter
def is_direct(request, organization):
    return pass_direct(request, organization=organization)


@register.filter
def is_manager(request, organization):
    return _valid_manager(
        request.user, Organization.objects.filter(slug=organization))


@register.filter
def is_provider(organization):
    return organization.plans.exists()


@register.filter
def is_site_owner(organization):
    return organization.pk == settings.PROVIDER_ID


@register.filter()
def manages_subscriber_to(user, plan):
    """
    Returns ``True`` if the user is a manager for an organization
    subscribed to plan.
    """
    return (user.is_authenticated()
            and user.manages.filter(subscriptions__plan=plan).exists())


@register.filter(needs_autoescape=False)
@stringfilter
def md(text): #pylint: disable=invalid-name
    return mark_safe(markdown.markdown(text,
        safe_mode='replace',
        html_replacement_text='<em>RAW HTML NOT ALLOWED</em>',
        enable_attributes=False))


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
def attached_manager(user):
    """
    Returns the person ``Organization`` associated to the user or None
    in none can be reliably found.
    """
    if isinstance(user, User):
        username = user.username
    elif isinstance(user, basestring):
        username = user
    else:
        return None
    queryset = Organization.objects.filter(slug=username)
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
    return user.manages.filter(is_active=True)[:8]


@register.filter()
def more_managed_organizations(user):
    """
    Returns True if the user manages more than 8 organizations.
    """
    return user.manages.filter(is_active=True).count() >= 8


@register.filter
def active_with_provider(organization, provider):
    """
    Returns a list of active subscriptions for organization for which provider
    is the owner of the plan.
    """
    return Subscription.objects.active_with_provider(organization, provider)


@register.filter(needs_autoescape=False)
def describe(transaction):
    return mark_safe(as_html_description(transaction))


@register.filter(needs_autoescape=False)
def refund_enable(transaction, user):
    """
    Returns True if *user* is able to trigger a refund on *transaction*.
    """
    subscription = Subscription.objects.filter(pk=transaction.event_id).first()
    if subscription:
        return _valid_manager(user, [subscription.plan.organization])
    return False


@register.filter()
def date_in_future(value, arg=None):
    if value:
        if arg:
            base = arg
        else:
            base = datetime.utcnow().replace(tzinfo=utc)
        if isinstance(value, long) or isinstance(value, int):
            value = datetime.fromtimestamp(value).replace(tzinfo=utc)
        if value > base:
            return True
    return False


@register.filter(needs_autoescape=False)
def product_url(organization, subscriber=None):
    return utils_product_url(organization, subscriber)
