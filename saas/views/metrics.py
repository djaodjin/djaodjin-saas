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

import json
from datetime import datetime, date, timedelta

from django.db.models.sql.query import RawQuery
from django.db.models import Count, Min, Sum, Max
from django.shortcuts import render, render_to_response, get_object_or_404
from django.utils.datastructures import SortedDict
from django.utils.timezone import utc
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from django.core.serializers.json import DjangoJSONEncoder

from saas.views.auth import valid_manager_for_organization
from saas.managers.metrics import aggregate_monthly_transactions, month_periods
from saas.models import (Organization, Plan, Subscription, Transaction,
    NewVisitors)
from saas.compat import User


class PlansMetricsView(TemplateView):
    """
    Performance of Plans for a time period
    (as a count of subscribers per plan per month)
    """

    template_name = 'saas/plan_metrics.html'

    def get_context_data(self, **kwargs):
        context = super(PlansMetricsView, self).get_context_data(**kwargs)
        organization = get_object_or_404(
            Organization, slug=kwargs.get('organization'))
        table = []
        for plan in Plan.objects.filter(organization=organization):
            values = []
            for end_period in month_periods(
                from_date=self.kwargs.get('from_date')):
                # XXX IMPLEMENT CODE take into account when subscription ends.
                values.append([end_period, Subscription.objects.filter(
                    plan=plan, created_at__lte=end_period,
                    ends_at__gt=end_period).count()])
            # XXX The template relies on "key" being plan.slug
            table.append({"key": plan.slug, "values": values})
        data = SortedDict()
        data['subscribers'] = {"title": "Active Subscribers",
                               "table": table}
        context.update({'title': "Plans",
            "organization": organization,
            "data": data,
            "data_json": json.dumps(data, cls=DjangoJSONEncoder)})
        return context


class RevenueMetricsView(TemplateView):
    """
    Generate a table of revenue (rows) per months (columns).
    """

    template_name = 'saas/revenue_metrics.html'

    def get_context_data(self, **kwargs):
        context = super(RevenueMetricsView, self).get_context_data(**kwargs)
        organization = get_object_or_404(
            Organization, slug=kwargs.get('organization'))
        from_date = kwargs.get('from_date', None)
        income_table, customer_table = aggregate_monthly_transactions(
            organization, from_date)
        data = SortedDict()
        data['amount'] = {"title": "Amount",
                          "unit": "$", "table": income_table}
        data['customers'] = {"title": "Customers", "table": customer_table}
        context = {"title": "Revenue Metrics",
                   "organization": organization,
                   "data": data,
                   "data_json": json.dumps(data, cls=DjangoJSONEncoder)}
        return context


@require_GET
def organization_usage(request, organization):
    organization = valid_manager_for_organization(request.user, organization)

    # Note: There is a way to get the result in a single SQL statement
    # but that requires to deal with differences in database backends
    # (MySQL: date_format, SQLite: strftime) and get around the
    # "Raw query must include the primary key" constraint.
    values = []
    today = date.today()
    end = datetime(day=today.day, month=today.month, year=today.year,
                            tzinfo=utc)
    for month in range(0, 12):
        first = datetime(day=1, month=end.month, year=end.year,
                                  tzinfo=utc)
        usages = Transaction.objects.filter(
            orig_organization=organization, orig_account='Usage',
            created_at__lt=first).aggregate(Sum('amount'))
        amount = usages.get('amount__sum', 0)
        if not amount:
            # The key could be associated with a "None".
            amount = 0
        values += [{"x": date.strftime(first, "%Y/%m/%d"),
                    "y": amount}]
        end = first - timedelta(days=1)
    context = {
        'data': [{"key": "Usage",
                 "values": values}],
        'organization_id': organization.slug}
    return render(request, "saas/usage_chart.html", context)


@require_GET
def organization_overall(request):

    organizations = Organization.objects.all()
    all_values = []

    for organization_all in organizations:
        organization = valid_manager_for_organization(
            request.user, organization_all)
        values = []
        today = date.today()
        end = datetime(day=today.day, month=today.month, year=today.year,
                                tzinfo=utc)

        for month in range(0, 12):
            first = datetime(day=1, month=end.month, year=end.year,
                                      tzinfo=utc)
            usages = Transaction.objects.filter(
                orig_organization=organization, orig_account='Usage',
                created_at__lt=first).aggregate(Sum('amount'))
            amount = usages.get('amount__sum', 0)
            if not amount:
                # The key could be associated with a "None".
                amount = 0
            values += [{"x": date.strftime(first, "%Y/%m/%d"),
                        "y": amount}]
            end = first - timedelta(days=1)
        all_values += [{"key": str(organization_all.slug), "values": values}]

    context = {'data' : all_values}

    return render(request, "saas/general_chart.html", context)


@require_GET
def statistic(request):
    # New vistor analyse
    newvisitor = NewVisitors.objects.all()

    if not newvisitor:
        return render_to_response("saas/stat.html")

    min_date = NewVisitors.objects.all().aggregate(Min('date'))
    max_date = NewVisitors.objects.all().aggregate(Max('date'))

    min_date = min_date.get('date__min', 0)
    max_date = max_date.get('date__max', 0)

    date_tabl = []

    for new in newvisitor:
        date_tabl += [{"x": new.date, "y": new.visitors_number}]

    for item in date_tabl:
        item["x"] = datetime.strftime(t["x"], "%Y/%m/%d")
        item["y"] = item["y"]/5

    current_date = min_date
    delta = timedelta(days=1)
    while current_date <= max_date:
        j = len(date_tabl)
        t = []
        for i in range(j):
            if date_tabl[i]["x"] == datetime.strftime(current_date, "%Y/%m/%d"):
                t += [i]
        if len(t) == 0:
            date_tabl += [{
                    "x": datetime.strftime(current_date, "%Y/%m/%d"), "y": 0}]
            current_date += delta
        else:
            current_date += delta

    date_tabl.sort()

    ########################################################
    # Conversion visitors to trial
    user = User.objects.all()
    date_joined_username = []
    for us in user:
        if (datetime.strftime(us.date_joined, "%Y/%m/%d")
            > datetime.strftime(min_date, "%Y/%m/%d") and
            datetime.strftime(us.date_joined, "%Y/%m/%d")
            < datetime.strftime(max_date, "%Y/%m/%d")):
            date_joined_username += [{
                    "date": us.date_joined, "user": str(us.username)}]

    user_per_joined_date = {}
    for datas in date_joined_username:
        key = datas["date"]
        if not key in user_per_joined_date:
            user_per_joined_date[key] = []
        user_per_joined_date[key] += [datas["user"]]

    trial = []
    for t in user_per_joined_date.keys():
        trial += [{"x": t, "y": len(user_per_joined_date[t])}]

    min_date_trial = User.objects.all().aggregate(Min('date_joined'))
    max_date_trial = User.objects.all().aggregate(Max('date_joined'))

    min_date_trial = min_date_trial.get('date_joined__min', 0)
    max_date_trial = max_date_trial.get('date_joined__max', 0)

    for t in trial:
        t["x"] = datetime.strftime(t["x"], "%Y/%m/%d")
    d = min_date
    delta = timedelta(days=1)
    while d <= max_date:
        j = len(trial)
        t = []
        for i in range(j):
            if trial[i]["x"] == datetime.strftime(d, "%Y/%m/%d"):
                t += [i]
        if len(t) == 0:
            trial += [{"x": datetime.strftime(d, "%Y/%m/%d"), "y": 0}]
            d += delta
        else:
            d += delta

    trial.sort()

    context = {'data' : [{"key": "Signup number",
                          "color": "#d62728",
                          "values": trial},
                         {"key": "New visitor number",
                          "values": date_tabl}]}
    return render_to_response("saas/stat.html", context)
