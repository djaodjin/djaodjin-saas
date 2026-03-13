# Copyright (c) 2026, DjaoDjin inc.
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

from ..compat import gettext_lazy as _
from ..models import Subscription


LOGGER = logging.getLogger(__name__)


def active_subscribers_by_period(plans=None, date_periods=None):
    """
    List of active subscribers for a set of *plans* for a specific time periods.
    """
    if date_periods is None:
        date_periods = []

    kwargs = {}
    if plans:
        kwargs = {'plan__in': plans}

    values = []
    for end_period in date_periods:
        values.append([end_period,
            Subscription.objects.active_at(end_period, **kwargs).count()])

    return values


def new_subscribers_by_period(plans=None, date_periods=None):
    """
    List of churn subscribers from the previous period for a set of *plans*
    for a specific time periods.
    """
    if date_periods is None:
        date_periods = []

    kwargs = {}
    if plans:
        kwargs = {'plan__in': plans}

    values = []
    start_period = date_periods[0]
    for end_period in date_periods[1:]:
        values.append([end_period, Subscription.objects.new_in_period(
            start_period, end_period, **kwargs).count()])
        start_period = end_period

    return values


def churn_subscribers_by_period(plans=None, date_periods=None):
    """
    List of churn subscribers from the previous period for a set of *plans*
    for a specific time periods.
    """
    if date_periods is None:
        date_periods = []

    kwargs = {}
    if plans:
        kwargs = {'plan__in': plans}

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


def subscribers_metrics(provider, date_periods):
    """
    Returns Total Subscribers, New Subscribers, and Churned Subscribers,
    formatted as a JSON response.

    .. code-block:: json

    {
        "title": "Amount",
        "scale": 0.01,
        "unit": "usd",
        "results": [
            {
                "slug": "total-subscribers",
                "title": "Total Subscribers",
                "values": [
                    ["2014-10-01T00:00:00Z", 1985716],
                    ["2014-11-01T00:00:00Z", 3516430],
                    ["2014-12-01T00:00:00Z", 3279451],
                    ["2015-01-01T00:00:00Z", 3787749],
                    ["2015-02-01T00:00:00Z", 4480875],
                    ["2015-03-01T00:00:00Z", 5495920],
                    ["2015-04-01T00:00:00Z", 7678976],
                    ["2015-05-01T00:00:00Z", 11064660],
                    ["2015-06-01T00:00:00Z", 10329043],
                    ["2015-07-01T00:00:00Z", 11444177],
                    ["2015-08-01T00:00:00Z", 10274412],
                    ["2015-08-06T04:59:14.721Z", 14106288]
                ]
            },
            {
                "slug": "new-subscribers",
                "title": "New Subscribers",
                "values": [
                    ["2014-10-01T00:00:00Z", 0],
                    ["2014-11-01T00:00:00Z", 0],
                    ["2014-12-01T00:00:00Z", 0],
                    ["2015-01-01T00:00:00Z", 0],
                    ["2015-02-01T00:00:00Z", 0],
                    ["2015-03-01T00:00:00Z", 0],
                    ["2015-04-01T00:00:00Z", 0],
                    ["2015-05-01T00:00:00Z", 0],
                    ["2015-06-01T00:00:00Z", 0],
                    ["2015-07-01T00:00:00Z", 0],
                    ["2015-08-01T00:00:00Z", 0],
                    ["2015-08-06T04:59:14.721Z", 0]
                ]
            },
            {
                "slug": "churned-subscribers",
                "title": "Churned Subscribers",
                "values": [
                    ["2014-10-01T00:00:00Z", 0],
                    ["2014-11-01T00:00:00Z", 0],
                    ["2014-12-01T00:00:00Z", 0],
                    ["2015-01-01T00:00:00Z", 0],
                    ["2015-02-01T00:00:00Z", 0],
                    ["2015-03-01T00:00:00Z", 0],
                    ["2015-04-01T00:00:00Z", 0],
                    ["2015-05-01T00:00:00Z", 0],
                    ["2015-06-01T00:00:00Z", 0],
                    ["2015-07-01T00:00:00Z", 0],
                    ["2015-08-01T00:00:00Z", 0],
                    ["2015-08-06T04:59:14.721Z", 0]
                ]
            }
        ]
    }
    """
    plans = provider.plans.all()
    active_subscribers = active_subscribers_by_period(
        plans=plans, date_periods=date_periods)
    new_subscribers = new_subscribers_by_period(
        plans=plans, date_periods=date_periods)
    churned_subscribers = churn_subscribers_by_period(
        plans=plans, date_periods=date_periods)

    resp = {
        'title': "Subscribers",
        'unit': 'profiles',
        'scale': 1,
        'results': [{
            "slug": "total-subscribers",
            "title": _("Total Subscribers"),
            "values": active_subscribers
        }, {
            "slug": "new-subscribers",
            "title": _("New Subscribers"),
            "values": new_subscribers
        }, {
            "slug": "churned-subscribers",
            "title": _("Churned Subscribers"),
            "values": churned_subscribers
        }]
    }
    return resp
