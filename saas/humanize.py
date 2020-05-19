# Copyright (c) 2020, DjaoDjin inc.
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


HOURLY = 1 # XXX to avoid import loop

DISCOUNT_PERCENTAGE = 1
DISCOUNT_CURRENCY = 2
DISCOUNT_PERIOD = 3


DESCRIBE_BALANCE = \
    "Balance on %(plan)s"

DESCRIBE_BUY_PERIODS = \
    "Subscription to %(plan)s until %(ends_at)s (%(humanized_periods)s)"

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

DESCRIBE_RETAINER_PERIODS = \
    "Retainer for services (%(humanized_periods)s)"

DESCRIBE_UNLOCK_NOW = \
    "Unlock %(plan)s now. Don't worry later to %(unlock_event)s."

DESCRIBE_UNLOCK_LATER = \
    "Access %(plan)s Today. Pay %(amount)s later to %(unlock_event)s."

DESCRIBE_WRITEOFF_LIABILITY = \
    "Write off liability for %(event)s"

DESCRIBE_WRITEOFF_RECEIVABLE = \
    "Write off receivable for %(event)s"


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


def describe_buy_periods(plan, ends_at, nb_periods, discount_by_types=None,
                         coupon=None, full_name=None):
    descr = ((DESCRIBE_BUY_PERIODS if plan.period_type != HOURLY
        else DESCRIBE_RETAINER_PERIODS) % {
                'plan': plan,
                'ends_at': datetime.datetime.strftime(ends_at, '%Y/%m/%d'),
                'humanized_periods': plan.humanize_period(nb_periods)})
    sep = ""
    descr_suffix = ""

    if not coupon and full_name:
        descr_suffix += "%s" % full_name

    if discount_by_types:
        discount_amount = discount_by_types.get(DISCOUNT_PERCENTAGE)
        if discount_amount:
            descr_suffix += sep + 'a %(percent)s discount' % {
                'percent': as_percentage(discount_amount)}
            sep = " and"
        discount_amount = discount_by_types.get(DISCOUNT_PERIOD)
        if discount_amount:
            descr_suffix += sep + '%(period)s free' % {
                'period': plan.humanize_period(discount_amount)}
            sep = " and"
        discount_amount = discount_by_types.get(DISCOUNT_CURRENCY)
        if discount_amount:
            descr_suffix += sep + 'a %(amount)s off' % {
                'amount': as_money(discount_amount, currency=plan.unit)}
            sep = " and"

    if coupon:
        if coupon.code.startswith('cpn_'):
            if full_name:
                descr_suffix += ', complimentary of %s' % full_name
        else:
            descr_suffix += '(code: %s)' % coupon.code

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
