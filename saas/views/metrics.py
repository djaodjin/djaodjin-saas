# Copyright (c) 2014, Fortylines LLC
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

import datetime, json, time
from time import mktime
from datetime import datetime, date, timedelta

from django.db.models.sql.query import RawQuery
from django.db.models import Count, Min, Sum, Avg, Max
from django.shortcuts import render_to_response
from django.views.decorators.http import require_GET
from django.utils.timezone import utc
from django.shortcuts import render, render_to_response
from django.views.decorators.http import require_GET
from django.views.generic.base import TemplateView
from django.core.serializers.json import DjangoJSONEncoder

from saas.views.auth import valid_manager_for_organization
from saas.models import Organization, Plan, Transaction, NewVisitors
from saas.compat import User


def month_periods(nb_months=12, from_date=None):
    """constructs a list of (nb_months + 1) dates in the past that fall
    on the first of each month until *from_date* which is the last entry
    of the list returned."""
    dates = []
    if not from_date:
        from_date = date.today()
    if isinstance(from_date, basestring):
        from_date = datetime.strptime(from_date, '%Y-%m')
    from_date = datetime(day=from_date.day, month=from_date.month,
                             year=from_date.year, tzinfo=utc)
    last = from_date
    dates.append(last)
    if last.day != 1:
        last = datetime(day=1, month=last.month, year=last.year, tzinfo=utc)
        dates.append(last)
        nb_months = nb_months - 1
    for index in range(0, nb_months):
        year = last.year
        month = last.month - 1
        if month < 1:
            year = last.year - month / 12 - 1
            month = 12 - (month % 12)
        last = datetime(day=1, month=month, year=year, tzinfo=utc)
        dates.append(last)
    dates.reverse()
    return dates


def aggregate_monthly(organization, account, from_date=None):
    """Returns a table of records over a period of 12 months *from_date*."""
    customers = []
    receivables = []
    new_customers = []
    new_receivables = []
    churn_customers = []
    churn_receivables = []
    queryset = None
    # We want to be able to compare *last* to *from_date* and not get django
    # warnings because timezones are not specified.
    dates = month_periods(13, from_date)
    first_date = dates[0]
    seam_date = dates[1]
    for last_date in dates[2:]:
        churn_query = RawQuery(
"""SELECT COUNT(DISTINCT(prev.dest_organization_id)), SUM(prev.amount)
       FROM saas_transaction prev
       LEFT OUTER JOIN (
         SELECT distinct(dest_organization_id)
           FROM saas_transaction
           WHERE created_at >= '%(seam_date)s'
         AND created_at < '%(last_date)s'
         AND orig_organization_id = '%(organization_id)s'
         AND orig_account = '%(account)s') curr
         ON prev.dest_organization_id = curr.dest_organization_id
       WHERE prev.created_at >= '%(first_date)s'
         AND prev.created_at < '%(seam_date)s'
         AND prev.orig_organization_id = '%(organization_id)s'
         AND prev.orig_account = '%(account)s'
         AND curr.dest_organization_id IS NULL""" % {
                "first_date": first_date,
                "seam_date": seam_date,
                "last_date": last_date,
                "organization_id": organization.id,
                "account": account }, 'default')
        churn_customer, churn_receivable = iter(churn_query).next()
        query_result = Transaction.objects.filter(
            orig_organization=organization,
            orig_account=account,
            created_at__gte=seam_date,
            created_at__lt=last_date).aggregate(
            Count('dest_organization', distinct=True),
            Sum('amount'))
        customer = query_result['dest_organization__count']
        receivable = query_result['amount__sum']
        new_query = RawQuery(
"""SELECT count(distinct(curr.dest_organization_id)), SUM(curr.amount)
   FROM saas_transaction curr
       LEFT OUTER JOIN (
         SELECT distinct(dest_organization_id)
           FROM saas_transaction
           WHERE created_at >= '%(first_date)s'
         AND created_at < '%(seam_date)s'
         AND orig_organization_id = '%(organization_id)s'
         AND orig_account = '%(account)s') prev
         ON curr.dest_organization_id = prev.dest_organization_id
       WHERE curr.created_at >= '%(seam_date)s'
         AND curr.created_at < '%(last_date)s'
         AND curr.orig_organization_id = '%(organization_id)s'
         AND curr.orig_account = '%(account)s'
         AND prev.dest_organization_id IS NULL""" % {
                "first_date": first_date,
                "seam_date": seam_date,
                "last_date": last_date,
                "organization_id": organization.id,
                "account": account }, 'default')
        new_customer, new_receivable = iter(new_query).next()
        period = last_date
        churn_customers += [ (period, churn_customer) ]
        churn_receivables += [ (period, - int(churn_receivable or 0)) ]
        customers += [ (period, customer) ]
        receivables += [ (period, int(receivable or 0)) ]
        new_customers += [ (period, new_customer) ]
        new_receivables += [ (period, int(new_receivable or 0)) ]
        first_date = seam_date
        seam_date = last_date
    return ((churn_customers, customers, new_customers),
            (churn_receivables, receivables, new_receivables))


def organization_monthly_revenue_customers(organization, from_date=None):
    """
    12 months of total/new/churn income and customers
    extracted from Transactions.
    """
    account = 'Income'
    customers, incomes = aggregate_monthly(organization, account, from_date)
    churned_custs, total_custs, new_custs = customers
    churned_income, total_income, new_income = incomes
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
                    period, nb_churned_custs * 100.0 / last_nb_total_custs) ]
        else:
            cust_churn_percent += [ (period, 0) ]
        last_nb_total_custs = nb_total_custs
    table = [ { "key": "Total %s" % account,
                "values": total_income
                },
              { "key": "%s from new Customers" % account,
                "values": new_income
                },
              { "key": "%s from churned Customers" % account,
                "values": churned_income
                },
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
              ]
    return table


class PlansMetricsView(TemplateView):
    """
    Performance of Plans for a time period
    (as a count of subscribers per plan per month)
    """

    template_name = 'saas/metrics_table.html'

    def get_context_data(self, **kwargs):
        context = super(PlansMetricsView, self).get_context_data(**kwargs)
        self.organization = self.kwargs.get('organization')
        table = []
        for plan in Plan.objects.filter(organization=self.organization):
            values = []
            for date in month_periods(from_date=self.kwargs.get('from_date')):
                # XXX IMPLEMENT CODE to filter subscriptions model by date!
                values.append([date, plan.subscribes.count()])
            table.append({ "key": plan.get_title(), "values": values })
        context.update({'title': "Plan Metrics",
                        'organization': self.organization, 'table': table,
                        "table_json": json.dumps(table, cls=DjangoJSONEncoder)})
        return context


@require_GET
def organization_engagement(request, organization, from_date=None):
    table = organization_monthly_revenue_customers(organization, from_date)
    context = { "title": "Revenue Metrics",
                "organization": organization, "table": table,
                "table_json": json.dumps(table, cls=DjangoJSONEncoder) }
    return render(request, "saas/metrics_table.html", context)

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
        amount = usages.get('amount__sum',0)
        if not amount:
            # The key could be associated with a "None".
            amount = 0
        values += [{ "x": date.strftime(first, "%Y/%m/%d"),
                   "y": amount }]
        end = first - timedelta(days=1)
    context = {
        'data': [{ "key": "Usage",
                 "values": values }],"organization_id":organization.name}
    return render(request, "saas/usage_chart.html", context)


@require_GET
def organization_overall(request):
    
    organizations = Organization.objects.all()
    all_values =[]
    
    for organization_all in organizations:
        organization = valid_manager_for_organization(request.user, organization_all)
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
            amount = usages.get('amount__sum',0)
            if not amount:
                # The key could be associated with a "None".
                amount = 0
            values += [{ "x": date.strftime(first, "%Y/%m/%d"),
                       "y": amount }]
            end = first - timedelta(days=1)
        all_values += [{"key":str(organization_all.name),"values":values}]

    context ={'data' : all_values}

    return render(request, "saas/general_chart.html", context)


@require_GET
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
