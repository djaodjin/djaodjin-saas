# Copyright (c) 2013, Sebastien Mirolo
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.

import datetime
import time
from time import mktime
from datetime import datetime, date, timedelta

from django.db.models import Sum,Count, Min, Sum, Avg,Max
from django.shortcuts import render_to_response
from django.views.decorators.http import require_GET
from django.utils.timezone import utc

from django.contrib.auth.models import User

from django.db.models import Sum,Min,Max
from django.shortcuts import render, render_to_response
from django.views.decorators.http import require_GET
from django.utils.timezone import utc

from saas.decorators import requires_agreement
from saas.views.auth import valid_manager_for_organization
from saas.models import Organization, Transaction, NewVisitors


def customers_aggregate(organization, first, last, prev_queryset=None):
    """Returns the number of unique customers between [first, last[ dates
    from transaction table."""
    queryset = Transaction.objects.filter(
        dest_organization=organization,
        created_at__gt=first, created_at__lt=last).values(
        'orig_organization')

    if prev_queryset:
        new_queryset = queryset.exclude(orig_organization=prev_queryset)
        churn_queryset = prev_queryset.exclude(orig_organization=queryset)
    else:
        new_queryset = queryset
        churn_queryset = Transaction.objects.none()

    return churn_queryset, queryset, new_queryset


def aggregate_monthly(organization, query_function):
    """Returns a table of records over a period of 12 months."""
    values = []
    new_values = []
    churn_values = []
    queryset = None
    today = datetime.date.today()
    # We want to be able to compare *last* to *today* and not get django
    # warnings because timezones are not specified.
    today = datetime.datetime(
        day=today.day, month=today.month, year=today.year, tzinfo=utc)
    first = datetime.datetime(
            day=1, month=today.month, year=today.year - 1, tzinfo=utc)
    for index in range(0, 12):
        year = first.year
        month = first.month + 1
        if month > 12:
            year = first.year + month / 12
            month = month % 12 + 1
        last = datetime.datetime(day=1, month=month, year=year, tzinfo=utc)
        if last > today:
            last = today
        churn_queryset, queryset, new_queryset = query_function(
            organization, first, last, queryset)
        churn_values += [ (last, churn_queryset.distinct().count()) ]
        values += [ (last, queryset.distinct().count()) ]
        new_values += [ (last, new_queryset.distinct().count()) ]
        first = last
    return churn_values, values, new_values


@require_GET
@requires_agreement('terms_of_use')
def organization_engagement(request, organization_id):
    organization = valid_manager_for_organization(request.user, organization_id)
    churned_custs, total_custs, new_custs = aggregate_monthly(
        organization, customers_aggregate)
    net_new_custs = []
    cust_churn_percent = []
    last_nb_total_custs = 0
    for index in range(0, 12):
        period, nb_total_custs = total_custs[index]
        period, nb_new_custs = new_custs[index]
        period, nb_churned_custs = churned_custs[index]
        net_new_custs += [ (period, nb_new_custs - nb_churned_custs) ]
        if last_nb_total_custs:
            cust_churn_percent += [ (
                    period, nb_churned_custs * 100 / last_nb_total_custs) ]
        else:
            cust_churn_percent += [ (period, 0) ]
        last_nb_total_custs = nb_total_custs
    context = {
        "organization": organization,
        "table": [
            { "key": "Total # of Customers",
              "values": total_custs
              },
            { "key": "# of new Customers",
              "values": new_custs
              },
            { "key": "# of churned Customers",
              "values": churned_custs
              },
            { "key": "Net New Customers",
              "values": net_new_custs
              },
            { "key": "% Customer Churn",
              "values": cust_churn_percent
              },
            ] }
    return render(request, "saas/engagement.html", context)

@require_GET
@requires_agreement('terms_of_use')
def organization_usage(request, organization_id):
    organization = valid_manager_for_organization(request.user, organization_id)

    # Note: There is a way to get the result in a single SQL statement
    # but that requires to deal with differences in database backends
    # (MySQL: date_format, SQLite: strftime) and get around the
    # "Raw query must include the primary key" constraint.
    values = []
    today = datetime.date.today()
    end = datetime.datetime(day=today.day, month=today.month, year=today.year,
                            tzinfo=utc)
    for month in range(0, 12):
        first = datetime.datetime(day=1, month=end.month, year=end.year,
                                  tzinfo=utc)
        usages = Transaction.objects.filter(
            orig_organization=organization, orig_account='Usage',
            created_at__lt=first).aggregate(Sum('amount'))
        amount = usages.get('amount__sum',0)
        if not amount:
            # The key could be associated with a "None".
            amount = 0
        values += [{ "x": datetime.date.strftime(first, "%Y/%m/%d"),
                   "y": amount }]
        end = first - datetime.timedelta(days=1)
    context = {
        'data': [{ "key": "Usage",
                 "values": values }],"organization_id":organization_id}
    return render(request, "saas/usage_chart.html", context)


@require_GET
@requires_agreement('terms_of_use')
def organization_overall(request):
    
    organizations = Organization.objects.all()
    all_values =[]
    
    for organization_all in organizations:
        organization = valid_manager_for_organization(request.user, organization_all)
        values = []
        today = datetime.date.today()
        end = datetime.datetime(day=today.day, month=today.month, year=today.year,
                                tzinfo=utc)
        
        for month in range(0, 12):
            first = datetime.datetime(day=1, month=end.month, year=end.year,
                                      tzinfo=utc)
            usages = Transaction.objects.filter(
                                                orig_organization=organization, orig_account='Usage',
                                                created_at__lt=first).aggregate(Sum('amount'))
            amount = usages.get('amount__sum',0)
            if not amount:
                # The key could be associated with a "None".
                amount = 0
            values += [{ "x": datetime.date.strftime(first, "%Y/%m/%d"),
                       "y": amount }]
            end = first - datetime.timedelta(days=1)
        all_values += [{"key":str(organization_all.name),"values":values}]

    context ={'data' : all_values}

    return render(request, "saas/general_chart.html", context)


@require_GET
@requires_agreement('terms_of_use')
def statistic(request):
    # New vistor analyse
    newvisitor = NewVisitors.objects.all()
    
    if not newvisitor:
        return render_to_response("saas/stat.html")
    
    Min_date = NewVisitors.objects.all().aggregate(Min('date'))
    Max_date = NewVisitors.objects.all().aggregate(Max('date'))
    
    Min_date = Min_date.get('date__min',0)
    Max_date = Max_date.get('date__max',0)
    
    date_tabl = []
    n={}
    
    for new in newvisitor:
        date_tabl +=[{"x":new.date,"y":new.visitors_number}]

    for t in date_tabl:
        t["x"] = datetime.strftime(t["x"],"%Y/%m/%d")
        t["y"] = t["y"]/5

    d = Min_date
    delta = timedelta(days=1)
    while d <= Max_date:
        j=len(date_tabl)
        t=[]
        for i in range(j):
            if date_tabl[i]["x"] == datetime.strftime(d,"%Y/%m/%d"):
                t +=[i]
        if len(t) == 0 :
            date_tabl += [{"x":datetime.strftime(d,"%Y/%m/%d"),"y":0}]
            d+=delta
        else :
            d+=delta

    date_tabl.sort()

    ########################################################
    # Conversion visitors to trial
    user = User.objects.all()
    date_joined_username =[]
    for us in user:
        if datetime.strftime(us.date_joined,"%Y/%m/%d")> datetime.strftime(Min_date,"%Y/%m/%d") and  datetime.strftime(us.date_joined,"%Y/%m/%d")< datetime.strftime(Max_date,"%Y/%m/%d"):
            date_joined_username += [{"date" : us.date_joined, "user":str(us.username)}]

    #print(rien)

    user_per_joined_date = {}
    for datas in date_joined_username:
        key  = datas["date"]
        if not key in user_per_joined_date:
            user_per_joined_date[key] = []
        user_per_joined_date[key]+= [datas["user"]]

    
    trial=[]
    for t in user_per_joined_date.keys():
        trial +=[{"x":t, "y":len(user_per_joined_date[t])}]

    Min_date_trial = User.objects.all().aggregate(Min('date_joined'))
    Max_date_trial = User.objects.all().aggregate(Max('date_joined'))

    Min_date_trial = Min_date_trial.get('date_joined__min',0)
    Max_date_trial = Max_date_trial.get('date_joined__max',0)
    
    for t in trial:
        t["x"] = datetime.strftime(t["x"],"%Y/%m/%d")
    d=Min_date
    delta = timedelta(days=1)
    while d <= Max_date:
        j=len(trial)
        t=[]
        for i in range(j):
            if trial[i]["x"] == datetime.strftime(d,"%Y/%m/%d"):
                t +=[i]
        if len(t) == 0 :
            trial += [{"x":datetime.strftime(d,"%Y/%m/%d"),"y":0}]
            d+=delta
        else :
            d+=delta
    
    trial.sort()
    
    context = {'data' : [{"key":"Signup number" , "color":"#d62728" , "values":trial},{"key":"New visitor number","values": date_tabl}]}
    
    return render_to_response("saas/stat.html", context)
