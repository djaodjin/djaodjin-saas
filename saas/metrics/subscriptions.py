# Copyright (c) 2023, DjaoDjin inc.
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

import logging

from django.db.models import F, Min, Max

from ..models import Subscription


LOGGER = logging.getLogger(__name__)


def active_subscribers_by_period(plan, date_periods=None):
    """
    List of active subscribers for a *plan* for a certain time period.
    """
    if date_periods is None:
        date_periods = []

    values = []
    for end_period in date_periods:
        values.append([end_period,
            Subscription.objects.active_at(end_period, plan=plan).count()])

    return values


def churn_subscribers_by_period(plan=None, date_periods=None):
    """
    List of churn subscribers from the previous period for a *plan*
    for specific time periods.
    """
    if date_periods is None:
        date_periods = []

    kwargs = {}
    if plan:
        kwargs = {'plan': plan}

    values = []
    start_period = date_periods[0]
    for end_period in date_periods[1:]:
        values.append([end_period, Subscription.objects.churn_in_period(
            start_period, end_period, **kwargs).count()])
        start_period = end_period

    return values


def subscribers_age(provider=None):
    if provider:
        queryset = Subscription.objects.filter(plan__organization=provider)
    else:
        queryset = Subscription.objects.all()
    return queryset.values(slug=F('organization__slug')).annotate(
        created_at=Min('created_at'), ends_at=Max('ends_at')).order_by(
        'organization__slug')
