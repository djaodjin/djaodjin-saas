# Copyright (c) 2016, DjaoDjin inc.
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

HOURLY = 1 # XXX to avoid import loop

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
    "Charge %(charge)s %(refund_type)s for %(descr)s"

DESCRIBE_DOUBLE_ENTRY_MATCH = \
    "Keep a balanced ledger"

DESCRIBE_LIABILITY_START_PERIOD = \
    "Past due"

DESCRIBE_OFFLINE_PAYMENT = \
    "Off-line payment"

DESCRIBE_RECOGNIZE_INCOME = \
    "Recognize %(subscription)s for %(nb_periods)s period to %(period_end)s"

DESCRIBE_RETAINER_PERIODS = \
    "Retainer for services (%(humanized_periods)s)"

DESCRIBE_UNLOCK_NOW = \
    "Unlock %(plan)s now. Don't worry later to %(unlock_event)s."

DESCRIBE_UNLOCK_LATER = \
    "Access %(plan)s Today. Pay %(amount)s later to %(unlock_event)s."


def as_money(value, currency='usd'):
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
        result = "(%s)" % result
    return result


def describe_buy_periods(plan, ends_at, nb_periods,
    discount_percent=0, descr_suffix=None):
    if plan.interval == HOURLY:
        descr = (DESCRIBE_RETAINER_PERIODS %
            {'plan': plan,
             'ends_at': datetime.datetime.strftime(ends_at, '%Y/%m/%d'),
             'humanized_periods': plan.humanize_period(nb_periods)})
    else:
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
