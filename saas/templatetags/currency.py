# Copyright (c) 2014, Fortylines LLC
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

import locale

from django import template

from saas.models import Plan


register = template.Library()


@register.filter()
def usd(value):
    if not value:
        return '$0.00'
    return '$%.2f' % (float(value) / 100)
    # XXX return locale.currency(value, grouping=True)


@register.filter()
def credits(value):
    return usd(abs(value))


@register.filter()
def debits(value):
    return usd(abs(value))


@register.filter()
def percentage(value):
    if not value:
        return '0 %%'
    return '%.1f %%' % (float(value) / 1000)

@register.filter()
def humanize_period(period):
    if period == Plan.INTERVAL_CHOICES[1][0]:
        return "per hour"
    elif period == Plan.INTERVAL_CHOICES[2][0]:
        return "per day"
    elif period == Plan.INTERVAL_CHOICES[3][0]:
        return "per week"
    elif period == Plan.INTERVAL_CHOICES[4][0]:
        return "per month"
    elif period == Plan.INTERVAL_CHOICES[5][0]:
        return "per quarter"
    elif period == Plan.INTERVAL_CHOICES[6][0]:
        return "per year"
    return "per ?"
