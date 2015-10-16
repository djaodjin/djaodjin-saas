# -*- coding: utf-8 -*-
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
import re

import markdown
from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.utils.timezone import utc

from saas.compat import User
from saas.humanize import  as_money, as_html_description
from saas.models import Organization, Subscription, Plan, get_broker
from saas.decorators import pass_direct, _valid_manager
from saas.utils import product_url as utils_product_url

register = template.Library()


@register.filter()
def htmlize_money(value, currency='usd'):
    text = as_money(value, currency)
    look = re.match(r'(\$|€|£)?(\d(\d|,)*)(\.\d+)?(.*)', text)
    if look:
        unit_prefix = '<span class="unit-prefix">%s</span>' % look.group(1)
        int_amount = look.group(2)
        frac_amount = look.group(4)
        unit_suffx = '<span class="unit-suffix">%s</span>' % look.group(5)
        if frac_amount == '.00':
            frac_amount = (
                '<span class="frac-digits zero-frac-digits">%s</span>'
                % frac_amount)
        else:
            frac_amount = ('<span class="frac-digits">%s</span>' % frac_amount)
        html = unit_prefix + int_amount + frac_amount + unit_suffx
        return  mark_safe(html)
    return text

@register.filter()
def humanize_money(value, currency):
    return as_money(value, currency)


@register.filter()
def humanize_balance(value, currency_unit):
    return humanize_money(abs(value), currency_unit)


@register.filter()
def percentage(value):
    if not value:
        return '0 %%'
    return '%.1f %%' % (float(value) / 100)


@register.filter()
def humanize_period(period):
    result = "per ?"
    if period == Plan.INTERVAL_CHOICES[0][0]:
        result = "per hour"
    elif period == Plan.INTERVAL_CHOICES[1][0]:
        result = "per day"
    elif period == Plan.INTERVAL_CHOICES[2][0]:
        result = "per week"
    elif period == Plan.INTERVAL_CHOICES[3][0]:
        result = "per month"
    elif period == Plan.INTERVAL_CHOICES[4][0]:
        result = "per quarter"
    elif period == Plan.INTERVAL_CHOICES[5][0]:
        result = "per year"
    return result


@register.filter()
def is_current_provider(organization):
    # We do a string compare here because both ``Organization`` might come
    # from a different db. That is if the organization parameter is not
    # a unicode string itself.
    slug = ''
    if isinstance(organization, basestring):
        slug = organization
    elif organization:
        slug = organization.slug
    return slug == get_broker().slug


@register.filter()
def is_debit(transaction, organization):
    """
    True if the transaction can be tagged as a debit. That is
    it is either payable by the organization or the transaction
    moves from a Funds account to the organization's Expenses account.
    """
    return transaction.is_debit(organization)


@register.filter()
def is_incomplete_month(date):
    return ((isinstance(date, basestring) and not date.endswith('01'))
        or (isinstance(date, datetime) and date.day != 1))


@register.filter
def is_direct(request, organization=None):
    if organization is None:
        organization = get_broker()
    return pass_direct(request, organization=organization)


@register.filter
def is_manager(request, organization):
    return _valid_manager(
        request.user, Organization.objects.filter(slug=organization))


@register.filter
def is_provider(organization): # XXX There is a field now.
    return organization.plans.exists()


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
    # XXX safe_mode is deprecated. Should we use bleach? As shown in example:
    # https://pythonhosted.org/Markdown/reference.html#markdown
    return mark_safe(markdown.markdown(text, enable_attributes=False))


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
def top_accessible_organizations(user):
    """
    Returns a queryset of the 8 most important organizations the user
    is a manager for.
    """
    return Organization.objects.accessible_by(user).filter(
        is_active=True)[:8]


@register.filter()
def more_accessible_organizations(user):
    """
    Returns True if the user manages more than 8 organizations.
    """
    return Organization.objects.accessible_by(user).filter(
        is_active=True).count() >= 8


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
    event = transaction.get_event()
    if event:
        return _valid_manager(user, [event.provider])
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
