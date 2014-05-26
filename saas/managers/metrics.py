# Copyright (c) 2014, DjaoDjin inc.
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

from datetime import datetime, timedelta

from django.db.models.sql.query import RawQuery
from django.db.models import Count, Sum
from django.utils.timezone import utc

from saas.models import Subscription, Transaction

def month_periods(nb_months=12, from_date=None):
    """constructs a list of (nb_months + 1) dates in the past that fall
    on the first of each month until *from_date* which is the last entry
    of the list returned."""
    dates = []
    if not from_date:
        # By default, we pick tomorrow so that income from Today shows up.
        from_date = datetime.utcnow().replace(tzinfo=utc) + timedelta(days=1)
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
    for _ in range(0, nb_months):
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
    """
    Returns a table of records over a period of 12 months *from_date*.
    """
    #pylint: disable=too-many-locals
    customers = []
    receivables = []
    new_customers = []
    new_receivables = []
    churn_customers = []
    churn_receivables = []
    # We want to be able to compare *last* to *from_date* and not get django
    # warnings because timezones are not specified.
    dates = month_periods(13, from_date)
    first_date = dates[0]
    seam_date = dates[1]
    for last_date in dates[2:]:
        churn_query = RawQuery(
"""SELECT COUNT(DISTINCT(prev.dest_organization_id)), SUM(prev.dest_amount)
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
                "account": account}, 'default')
        churn_customer, churn_receivable = iter(churn_query).next()
        query_result = Transaction.objects.filter(
            orig_organization=organization,
            orig_account=account,
            created_at__gte=seam_date,
            created_at__lt=last_date).aggregate(
            Count('dest_organization', distinct=True),
            Sum('dest_amount'))
        customer = query_result['dest_organization__count']
        receivable = query_result['dest_amount__sum']
        new_query = RawQuery(
"""SELECT count(distinct(curr.dest_organization_id)), SUM(curr.dest_amount)
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
                "account": account}, 'default')
        new_customer, new_receivable = iter(new_query).next()
        period = last_date
        churn_customers += [(period, churn_customer)]
        churn_receivables += [(period, int(churn_receivable or 0))]
        customers += [(period, customer)]
        receivables += [(period, int(receivable or 0))]
        new_customers += [(period, new_customer)]
        new_receivables += [(period, int(new_receivable or 0))]
        first_date = seam_date
        seam_date = last_date
    return ((churn_customers, customers, new_customers),
            (churn_receivables, receivables, new_receivables))


def aggregate_monthly_transactions(organization, from_date=None):
    """
    12 months of total/new/churn income and customers
    extracted from Transactions.
    """
    #pylint: disable=too-many-locals
    account = Transaction.INCOME
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
        net_new_custs += [(period, nb_new_custs - nb_churned_custs)]
        if last_nb_total_custs:
            cust_churn_percent += [(period,
                round(nb_churned_custs * 100.0 / last_nb_total_custs, 2))]
        else:
            cust_churn_percent += [(period, 0)]
        last_nb_total_custs = nb_total_custs
    income_table = [{"key": "Total %s" % account,
                     "values": total_income
                     },
                    {"key": "%s from new Customers" % account,
                     "values": new_income
                     },
                    {"key": "%s lost from churned Customers" % account,
                     "values": churned_income
                     },
                    ]
    customer_table = [{"key": "Total # of Customers",
                       "values": total_custs
                       },
                      {"key": "# of new Customers",
                       "values": new_custs
                       },
                      {"key": "# of churned Customers",
                       "values": churned_custs
                       },
                      {"key": "Net New Customers",
                       "values": net_new_custs
                       },
                      ]
    customer_extra = [{"key": "% Customer Churn",
                       "values": cust_churn_percent
                       },
                      ]
    return income_table, customer_table, customer_extra


def active_subscribers(plan, from_date=None):
    """
    List of active subscribers for a *plan*.
    """
    values = []
    for end_period in month_periods(from_date=from_date):
        values.append([end_period, Subscription.objects.filter(
            plan=plan, created_at__lte=end_period,
            ends_at__gt=end_period).count()])
    return values


def churn_subscribers(plan=None, from_date=None):
    """
    List of churn subscribers from the previous period for a *plan*.
    """
    values = []
    dates = month_periods(13, from_date)
    start_period = dates[0]
    if plan:
        for end_period in dates[1:]:
            values.append([end_period, Subscription.objects.filter(plan=plan,
                ends_at__gte=start_period, ends_at__lt=end_period).count()])
            start_period = end_period
    else:
        for end_period in dates[1:]:
            values.append([end_period, Subscription.objects.filter(
                ends_at__gte=start_period, ends_at__lt=end_period).count()])
            start_period = end_period
    return values
