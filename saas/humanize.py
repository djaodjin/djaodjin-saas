# Copyright (c) 2022, DjaoDjin inc.
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

import datetime, re

from . import settings
from .compat import gettext_lazy as _

# prevents an import loop with models.py
HOURLY = 1
DAILY = 2
WEEKLY = 3
MONTHLY = 4
YEARLY = 5

DISCOUNT_PERCENTAGE = 1
DISCOUNT_CURRENCY = 2
DISCOUNT_PERIOD = 3


DESCRIBE_BALANCE = \
    "Balance on %(plan)s"

DESCRIBE_BUY_PERIODS = \
   "Subscription to %(plan)s until %(ends_at)s (%(nb_periods)s %(period_name)s)"

DESCRIBE_BUY_USE = \
    "Buy %(quantity)s %(plan)s %(use_charge)s"

DESCRIBE_CHARGED_CARD = \
    "Charge %(charge)s on credit card of %(organization)s"

DESCRIBE_CHARGED_CARD_PROCESSOR = \
    "Charge %(charge)s processor fee for %(event)s"

DESCRIBE_CHARGED_CARD_BROKER = \
    "Charge %(charge)s broker fee for %(event)s"

DESCRIBE_CHARGED_CARD_PROVIDER = \
    "Charge %(charge)s distribution for %(event)s"

DESCRIBE_CHARGED_CARD_REFUND = \
    "Charge %(charge)s %(refund_type)s for %(descr)s"

DESCRIBE_DOUBLE_ENTRY_MATCH = \
    "Keep a balanced ledger"

DESCRIBE_LIABILITY_START_PERIOD = \
    "Past due"

DESCRIBE_OFFLINE_PAYMENT = \
    "Off-line payment"

DESCRIBE_RECOGNIZE_INCOME = \
    "Recognize %(subscription)s from %(period_start)s to %(period_end)s"

DESCRIBE_RECOGNIZE_INCOME_DETAILED = \
    "Recognize %(subscription)s from %(period_start)s to %(period_end)s"\
    " (%(nb_periods)s period)"

DESCRIBE_UNLOCK_NOW = \
    "Unlock %(plan)s now. Don't worry later to %(unlock_event)s."

DESCRIBE_UNLOCK_LATER = \
    "Access %(plan)s Today. Pay %(amount)s later to %(unlock_event)s."

DESCRIBE_WRITEOFF_LIABILITY = \
    "Write off liability for %(event)s"

DESCRIBE_WRITEOFF_RECEIVABLE = \
    "Write off receivable for %(event)s"

DESCRIBE_SUFFIX_DISCOUNT_PERCENTAGE = \
    "a %(percent)s discount"

DESCRIBE_SUFFIX_DISCOUNT_PERIOD = \
    "%(nb_periods)s %(period_name)s free"

DESCRIBE_SUFFIX_DISCOUNT_CURRENCY = \
    "a %(amount)s off"

DESCRIBE_SUFFIX_TARGET_SUBSCRIBER = \
    "for %(subscriber_full_name)s (%(sync_on)s)"

DESCRIBE_SUFFIX_GROUP_BUY = \
    ", complimentary of %(payer)s"

DESCRIBE_SUFFIX_COUPON_APPLIED = \
    " (code: %(code)s)"


REGEXES = {
    'amount': r'(?P<amount>\S+)',
    'charge': r'(?P<charge>\S+)',
    'code': r'(?P<code>\S+)',
    'descr': r'(?P<descr>.*)',
    'event': r'(?P<event>\S+)',
    'ends_at': r'(?P<ends_at>\S+)',
    'nb_periods': r'(?P<nb_periods>\d+)',
    'organization': r'(?P<organization>\S+)',
    'payer': r'(?P<payer>\S+)',
    'percent': r'(?P<percent>\S+)',
    'period_end': r'(?P<period_end>\S+)',
    'period_name': r'(?P<period_name>\S+)',
    'period_start': r'(?P<period_start>\S+)',
    'plan': r'(?P<plan>\S+)',
    'quantity': r'(?P<quantity>\d+)',
    'refund_type': r'(?P<refund_type>\S+)',
    'subscriber_full_name': r'(?P<subscriber_full_name>(\S| )+)',
    'subscription': r'(?P<subscriber>\S+):(?P<plan>\S+)',
    'sync_on': r'(?P<sync_on>\S+)',
    'use_charge': r'(?P<use_charge>\S+)',
    'unlock_event': r'(?P<unlock_event>\S+)',
}

# Implementation note: The text has been copied verbatim instead
# of using the environment variable declared such that the translation
# module is able to pick up those strings and add them in the .po file.
REGEX_TO_TRANSLATION = {
    (DESCRIBE_BALANCE % REGEXES): \
_("Balance on %(plan)s"),
    (DESCRIBE_BUY_PERIODS.replace(' (', r' \(').replace(
        ')s)', r')s\)') % REGEXES):\
_("Subscription to %(plan)s until %(ends_at)s"\
" (%(nb_periods)s %(period_name)s)"),
    (DESCRIBE_BUY_USE % REGEXES): \
_("Buy %(quantity)s %(plan)s %(use_charge)s"),
    (DESCRIBE_CHARGED_CARD % REGEXES): \
_("Charge %(charge)s on credit card of %(organization)s"),
    (DESCRIBE_CHARGED_CARD_PROCESSOR % REGEXES): \
_("Charge %(charge)s processor fee for %(event)s"),
    (DESCRIBE_CHARGED_CARD_BROKER % REGEXES): \
_("Charge %(charge)s broker fee for %(event)s"),
    (DESCRIBE_CHARGED_CARD_PROVIDER % REGEXES): \
_("Charge %(charge)s distribution for %(event)s"),
    (DESCRIBE_CHARGED_CARD_REFUND % REGEXES): \
_("Charge %(charge)s %(refund_type)s for %(descr)s"),
    (DESCRIBE_DOUBLE_ENTRY_MATCH % REGEXES): \
_("Keep a balanced ledger"),
    (DESCRIBE_LIABILITY_START_PERIOD % REGEXES): \
_("Past due"),
    (DESCRIBE_OFFLINE_PAYMENT % REGEXES): \
_("Off-line payment"),
    (DESCRIBE_RECOGNIZE_INCOME_DETAILED.replace(' (', r' \(').replace(
        'period)', r'period\)') % REGEXES): \
_("Recognize %(subscription)s from %(period_start)s to %(period_end)s"\
    " (%(nb_periods)s period)"),
    (DESCRIBE_RECOGNIZE_INCOME % REGEXES): \
_("Recognize %(subscription)s from %(period_start)s to %(period_end)s"),
    (DESCRIBE_UNLOCK_NOW % REGEXES): \
_("Unlock %(plan)s now. Don't worry later to %(unlock_event)s."),
    (DESCRIBE_UNLOCK_LATER % REGEXES): \
_("Access %(plan)s Today. Pay %(amount)s later to %(unlock_event)s."),
    (DESCRIBE_WRITEOFF_LIABILITY % REGEXES): \
_("Write off liability for %(event)s"),
    (DESCRIBE_WRITEOFF_RECEIVABLE % REGEXES): \
_("Write off receivable for %(event)s"),
}


def as_money(value, currency=settings.DEFAULT_UNIT, negative_format="(%s)"):
    unit_prefix = ''
    unit_suffix = ''
    negative = False
    if currency:
        if currency.startswith('-'):
            negative = True
            currency = currency[1:]
        currency = currency.lower()
        if currency in ['usd', 'cad']:
            unit_prefix = '$'
            if currency != 'usd':
                unit_suffix = ' %s' % currency
        elif currency in ['eur']:
            unit_prefix = '\u20ac'
        else:
            unit_suffix = ' %s' % currency
    grouped = ""
    if value < 0:
        value = - value
        negative = True
    text = '%d' % value
    if len(text) > 2:
        int_part = text[:-2]
        frac_part = text[-2:]
        idx = len(int_part)
        while idx > 3:
            grouped += ',' + int_part[idx - 3:idx]
            idx -= 3
        int_part = int_part[0:idx]
    else:
        int_part = '0'
        frac_part = '%02d' % value
    result = (unit_prefix + int_part + grouped + '.' + frac_part + unit_suffix)
    if negative:
        result = negative_format % result
    return result


def as_percentage(value):
    if (value % 100) == 0:
        return "%d%%" % (value // 100)
    return "%.2f%%" % (value / 100)


def _describe_period_name(period_type, nb_periods):
    result = None
    if period_type == HOURLY:
        result = 'hour'
    elif period_type == DAILY:
        result = 'day'
    elif period_type == WEEKLY:
        result = 'week'
    elif period_type == MONTHLY:
        result = 'month'
    elif period_type == YEARLY:
        result = 'year'
    if result and nb_periods > 1:
        result += 's'
    return result


def translate_period_name(period_name, nb_periods):
    result = None
    if period_name.startswith('hour'):
        result = _('hour')
    elif period_name.startswith('day'):
        result = _('day')
    elif period_name.startswith('week'):
        result = _('week')
    elif period_name.startswith('month'):
        result = _('month')
    elif period_name.startswith('year'):
        result = _('year')
    if result and nb_periods > 1 and not result.endswith('s'):
        result += 's'
    return result


def translate_descr_suffix(descr):
    pos = descr.rfind(' - ')
    if pos >= 0:
        descr_suffix = descr[pos + 3:]
        descr = descr[:pos]
    else:
        # If we cannot find the suffix separator (' - '), we assume the whole
        # string passed as parameter is the description suffix.
        descr_suffix = descr
        descr = ""
    pat = r"(a %(percent)s discount)?( and )?"\
        r"(%(nb_periods)s %(period_name)s free)?( and )?"\
        r"(a %(amount)s off)?"\
        r"(, complimentary of %(payer)s)?"\
        r"(\s*for %(subscriber_full_name)s \(%(sync_on)s\))?"\
        r"( \(code: %(code)s\))?" % REGEXES
    look = re.match(pat, descr_suffix)
    if look:
        descr_suffix = ""
        # Implementation note: The text has been copied verbatim instead
        # of using the environment variable declared such that the translation
        # module is able to pick up those strings and add them in the .po file.
        sep = ""
        percent = look.group('percent')
        if percent:
            descr_suffix += sep + _(DESCRIBE_SUFFIX_DISCOUNT_PERCENTAGE) % {
                'percent': percent}
            sep = _(" and ")
        nb_periods = look.group('nb_periods')
        period_name = look.group('period_name')
        if nb_periods and period_name:
            nb_periods = int(nb_periods)
            descr_suffix += sep + _(DESCRIBE_SUFFIX_DISCOUNT_PERIOD) % {
                'nb_periods': nb_periods,
                'period_name': translate_period_name(period_name, nb_periods)}
            sep = _(" and ")
        amount = look.group('amount')
        if amount:
            descr_suffix += sep + _(DESCRIBE_SUFFIX_DISCOUNT_CURRENCY) % {
                'amount': amount}
            sep = _(" and ")
        payer = look.group('payer')
        if payer:
            descr_suffix += _(", complimentary of %(payer)s") % {'payer': payer}
        subscriber_full_name = look.group('subscriber_full_name')
        sync_on = look.group('sync_on')
        if subscriber_full_name and sync_on:
            descr_suffix += " " + _(DESCRIBE_SUFFIX_TARGET_SUBSCRIBER) % {
                'subscriber_full_name': subscriber_full_name,
                'sync_on': sync_on
            }
        code = look.group('code')
        if code:
            descr_suffix += _(DESCRIBE_SUFFIX_COUPON_APPLIED) % {'code': code}

    if descr_suffix:
        descr += " - %s" % descr_suffix
    return descr


def describe_buy_periods(plan, ends_at, nb_periods, discount_by_types=None,
                         coupon=None, cart_item=None, full_name=None):
    #pylint:disable=too-many-arguments
    descr = DESCRIBE_BUY_PERIODS % {
        'plan': plan,
        'ends_at': datetime.datetime.strftime(ends_at, '%Y/%m/%d'),
        'nb_periods': nb_periods,
        'period_name': _describe_period_name(plan.period_type, nb_periods)}
    sep = ""
    descr_suffix = ""

    # triggered by `new_subscription_order` through the renewals
    # process (amount is None).
    # XXX It seems to be able to figure out which account was billed
    # when receiving multiple receipts.
    if full_name:
        descr_suffix += "%s" % full_name

    if coupon and not discount_by_types:
        discount_by_types = {}
        discount_by_types[coupon.discount_type] = coupon.discount_value

    if discount_by_types:
        discount_amount = discount_by_types.get(DISCOUNT_PERCENTAGE)
        if discount_amount:
            descr_suffix += sep + DESCRIBE_SUFFIX_DISCOUNT_PERCENTAGE % {
                'percent': as_percentage(discount_amount)}
            sep = " and "
        discount_amount = discount_by_types.get(DISCOUNT_PERIOD)
        if discount_amount:
            descr_suffix += sep + DESCRIBE_SUFFIX_DISCOUNT_PERIOD % {
                'nb_periods': discount_amount,
                'period_name': _describe_period_name(
                    plan.period_type, discount_amount)}
            sep = " and "
        discount_amount = discount_by_types.get(DISCOUNT_CURRENCY)
        if discount_amount:
            descr_suffix += sep + DESCRIBE_SUFFIX_DISCOUNT_CURRENCY % {
                'amount': as_money(discount_amount, currency=plan.unit)}
            sep = " and "

    if coupon:
        if coupon.code.startswith('cpn_'):
            # We have switched the full_name from the target subscriber
            # to the group buyer in `execute_order`.
            if cart_item and cart_item.full_name:
                descr_suffix += DESCRIBE_SUFFIX_GROUP_BUY % {
                    'payer': full_name}
        else:
            descr_suffix += DESCRIBE_SUFFIX_COUPON_APPLIED % {
                'code': coupon.code}

    if cart_item and cart_item.sync_on:
        # We also set sync_on to None in `execute_order`, so both
        # above DESCRIBE_SUFFIX_GROUP_BUY and here cannot happen
        # at the same time.
        if descr_suffix:
            descr_suffix += " "
        descr_suffix += DESCRIBE_SUFFIX_TARGET_SUBSCRIBER % {
            'subscriber_full_name': cart_item.full_name,
            'sync_on': cart_item.sync_on}

    if descr_suffix:
        descr += " - %s" % descr_suffix
    return descr


def describe_buy_use(use_charge, quantity,
                     discount_percent=0, descr_suffix=None):
    descr = (DESCRIBE_BUY_USE % {
        'plan': use_charge.plan,
        'use_charge': use_charge.title,
        'quantity': quantity})
    if discount_percent:
        last_suffix = descr_suffix
        descr_suffix = DESCRIBE_SUFFIX_DISCOUNT_PERCENTAGE % {
            'percent': discount_percent}
        if last_suffix:
            descr_suffix = '%s %s' % (descr_suffix, last_suffix)
    if descr_suffix:
        descr += '- %s' % descr_suffix
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
