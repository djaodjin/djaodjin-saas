# -*- coding: utf-8 -*-
# Copyright (c) 2021, DjaoDjin inc.
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
from __future__ import unicode_literals

from datetime import datetime, timedelta
import re

import markdown
from django import template
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.utils.timezone import utc

from ..compat import gettext_lazy as _, six
from ..decorators import fail_direct, _valid_manager
from ..humanize import as_money, as_percentage
from ..mixins import as_html_description, product_url as utils_product_url
from ..models import Plan, Price, Subscription, get_broker
from ..utils import get_organization_model

register = template.Library()

@register.filter
def active_with_provider(organization, provider):
    """
    Returns a list of active subscriptions for organization for which provider
    is the owner of the plan.
    """
    return Subscription.objects.active_with(provider).filter(
        organization=organization)


@register.filter()
def date_in_future(value, arg=None):
    if value:
        if arg:
            base = arg
        else:
            base = datetime.utcnow().replace(tzinfo=utc)
        if isinstance(value, six.integer_types):
            value = datetime.fromtimestamp(value).replace(tzinfo=utc)
        if value > base:
            return True
    return False


@register.filter(needs_autoescape=False)
def describe(transaction):
    try:
        return transaction['description']
    except (TypeError, KeyError):
        pass
    return mark_safe(as_html_description(transaction))


@register.filter(needs_autoescape=False)
def describe_no_links(transaction):
    return mark_safe(as_html_description(transaction, active_links=False))


@register.filter()
def price(item):
    return Price(item['amount'], item['unit'])


@register.filter()
def dest_price(item):
    return Price(item['dest_amount'], item['dest_unit'])


@register.filter()
def orig_price(item):
    return Price(item['orig_amount'], item['orig_unit'])


@register.filter()
def isoformat(val):
    if isinstance(val, datetime):
        return val.isoformat()
    return val


@register.filter()
def iteritems(val):
    return six.iteritems(val)


@register.filter()
def htmlize_money(amount_unit_tuple):
    text = as_money(amount_unit_tuple.amount, amount_unit_tuple.unit)
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
def humanize_money(amount_unit_tuple):
    return as_money(amount_unit_tuple.amount, amount_unit_tuple.unit)

@register.filter()
def humanize_percent(percentage):
    return as_percentage(percentage)

@register.filter()
def humanize_period(period):
    result = _("per ?")
    if period == Plan.INTERVAL_CHOICES[0][0]:
        result = _("per hour")
    elif period == Plan.INTERVAL_CHOICES[1][0]:
        result = _("per day")
    elif period == Plan.INTERVAL_CHOICES[2][0]:
        result = _("per week")
    elif period == Plan.INTERVAL_CHOICES[3][0]:
        result = _("per month")
    elif period == Plan.INTERVAL_CHOICES[4][0]:
        result = _("per year")
    return result


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
    return ((isinstance(date, six.string_types) and not date.endswith('01'))
        or (isinstance(date, datetime) and date.day != 1))


@register.filter
def is_direct(request, organization=None):
    if organization is None:
        organization = get_broker()
    return not fail_direct(request, organization=organization)


@register.filter
def is_manager(request, organization):
    organization_model = get_organization_model()
    if not isinstance(organization, organization_model):
        organization = get_object_or_404(organization_model, slug=organization)
    return _valid_manager(request, [organization])


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
    return datetime.strftime(last_date, "%b'%y") + "*"


@register.filter()
def attached_organization(user):
    """
    Returns the person ``Organization`` associated to the user or None
    in none can be reliably found.
    """
    return get_organization_model().objects.attached(user)


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


@register.filter(needs_autoescape=False)
def product_url(organization, subscriber=None):
    return utils_product_url(organization, subscriber)


@register.filter()
def short_date(val):
    if isinstance(val, datetime):
        return val.strftime("%b %d, %Y")
    return val
