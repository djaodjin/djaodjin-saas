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

import datetime, re

from django.core.urlresolvers import reverse

from saas.utils import product_url


DESCRIBE_BALANCE = \
    "Balance on %(plan)s"

DESCRIBE_BUY_PERIODS = \
    "Subscription to %(plan)s until %(ends_at)s (%(humanized_periods)s)"

DESCRIBE_CHARGED_CARD = \
    "Charge %(charge)s on credit card of %(organization)s"

DESCRIBE_CHARGED_CARD_PROCESSOR = \
    "Charge %(charge)s processor fee for %(event)s"

DESCRIBE_CHARGED_CARD_PROVIDER = \
    "Charge %(charge)s distribution for %(event)s"

DESCRIBE_CHARGED_CARD_REFUND = \
    "Charge %(charge)s refund for %(descr)s"

DESCRIBE_UNLOCK_NOW = \
    "Unlock %(plan)s now. Don't worry later to %(unlock_event)s."

DESCRIBE_UNLOCK_LATER = \
    "Access %(plan)s Today. Pay %(amount)s later to %(unlock_event)s."


def as_money(value, currency='usd'):
    if value == 0:
        return '0.00'
    if currency.startswith('-'):
        value = - value
        currency = currency[1:]
    currency = currency.lower()
    if currency == 'cad':
        return '$%.2f CAD' % (float(value) / 100)
    return '$%.2f' % (float(value) / 100)
    # XXX return locale.currency(value, grouping=True)


def describe_buy_periods(plan, ends_at, nb_periods,
    discount_percent=0, descr_suffix=None):
    descr = (DESCRIBE_BUY_PERIODS %
        {'plan': plan,
         'ends_at': datetime.datetime.strftime(ends_at, '%Y/%m/%d'),
         'humanized_periods': plan.humanize_period(nb_periods)})
    if discount_percent:
        descr += ' - a %d%% discount' % discount_percent
    if descr_suffix:
        descr += ' %s' % descr_suffix
    return descr


def match_unlock(descr):
    look = re.match(DESCRIBE_UNLOCK_NOW % {
            'plan': r'(?P<plan>\S+)', 'unlock_event': r'.*'}, descr)
    if not look:
        look = re.match(DESCRIBE_UNLOCK_LATER % {
            'plan': r'(?P<plan>\S+)', 'unlock_event': r'.*',
            'amount': r'.*'}, descr)
    if not look:
        return False
    return True


def as_html_description(transaction, provider=None):
    """
    ``DESCRIBE_BALANCE`` transactions contain subscriber on both sides
    (orig_organization and dest_organization). We thus pass provider
    as an extra parameter to create URLs.
    """

    if provider is None:
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
            return transaction.descr.replace(look.group('charge'), link)
        return transaction.descr

    plan_link = ('<a href="%s%s/">%s</a>' % (
        product_url(provider, subscriber),
        look.group('plan'), look.group('plan')))
    return transaction.descr.replace(look.group('plan'), plan_link)
