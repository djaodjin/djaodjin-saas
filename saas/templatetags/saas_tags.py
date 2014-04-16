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

import re

from django import template
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe

from saas.humanize import (DESCRIBE_BALANCE, DESCRIBE_BUY_PERIODS,
    DESCRIBE_CHARGED_CARD, DESCRIBE_UNLOCK_NOW, DESCRIBE_UNLOCK_LATER)
from saas.views.auth import valid_manager_for_organization

register = template.Library()

@register.filter
def is_manager(request, organization):
    if not organization:
        organization = request.client
    try:
        valid_manager_for_organization(request.user, organization)
    except PermissionDenied:
        return False
    return True


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
        look = re.match(DESCRIBE_CHARGED_CARD  % {
            'charge': r'(?P<charge>\S+)', 'organization': r'.*'},
            transaction.descr)
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

