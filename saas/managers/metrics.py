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

from datetime import datetime

from django.db import router
from django.db.models.sql.query import RawQuery
from django.db.models import Count, Sum
from django.utils.dateparse import parse_datetime
from django.utils.timezone import utc

from ..models import Plan, Subscription, Transaction
from ..utils import datetime_or_now


def month_periods(nb_months=12, from_date=None, step_months=1):
    """constructs a list of (nb_months + 1) dates in the past that fall
    on the first of each month until *from_date* which is the last entry
    of the list returned."""
    dates = []
    if from_date and isinstance(from_date, basestring):
        from_date = parse_datetime(from_date)
    from_date = datetime_or_now(from_date)
    dates.append(from_date)
    last = datetime(
        day=from_date.day, month=from_date.month, year=from_date.year,
        tzinfo=utc)
    if last.day != 1:
        last = datetime(day=1, month=last.month, year=last.year, tzinfo=utc)
        dates.append(last)
        nb_months = nb_months - 1
    for _ in range(0, nb_months, step_months):
        year = last.year
        month = last.month - step_months
        if month < 1:
            if month % 12 == 0:
                year = last.year + month / 12 - 1
                month = 12
            else:
                year = last.year + month / 12
                month = month % 12
        last = datetime(day=1, month=month, year=year, tzinfo=utc)
        dates.append(last)
    dates.reverse()
    return dates


def aggregate_monthly(organization, account,
                      from_date=None, orig='orig', dest='dest', **kwargs):
    # pylint: disable=too-many-locals
    counts = []
    amounts = []
    # We want to be able to compare *last* to *from_date* and not get django
    # warnings because timezones are not specified.
    dates = month_periods(13, from_date)
    period_start = dates[1]
    for period_end in dates[2:]:
        # A bit ugly but it does the job ...
        kwargs.update({'%s_organization' % orig: organization,
            '%s_account' % orig: account})
        query_result = Transaction.objects.filter(
            created_at__gte=period_start,
            created_at__lt=period_end, **kwargs).aggregate(
            Count('%s_organization' % dest, distinct=True),
            Sum('%s_amount' % dest))
        count = query_result['%s_organization__count' % dest]
        amount = query_result['%s_amount__sum' % dest]
        period = period_end
        counts += [(period, count)]
        amounts += [(period, int(amount or 0))]
        period_start = period_end
    return (counts, amounts)


def aggregate_monthly_churn(organization, account, interval,
                            from_date=None, orig='orig', dest='dest'):
    """
    Returns a table of records over a period of 12 months *from_date*.
    """
    #pylint: disable=too-many-locals,too-many-arguments
    customers = []
    receivables = []
    new_customers = []
    new_receivables = []
    churn_customers = []
    churn_receivables = []
    # We want to be able to compare *last* to *from_date* and not get django
    # warnings because timezones are not specified.
    dates = month_periods(13, from_date)
    trail_period_start = dates[0]
    period_start = dates[1]
    for period_end in dates[2:]:
        if interval == Plan.YEARLY:
            prev_period_start = datetime(
                day=period_start.day, month=period_start.month,
                year=period_start.year - 1, tzinfo=period_start.tzinfo)
            prev_period_end = datetime(
                day=period_end.day, month=period_end.month,
                year=period_end.year - 1, tzinfo=period_end.tzinfo)
        else:
            # default to monthly
            prev_period_start = trail_period_start
            prev_period_end = period_start
        churn_query = RawQuery(
"""SELECT COUNT(DISTINCT(prev.%(dest)s_organization_id)),
          SUM(prev.%(dest)s_amount)
       FROM saas_transaction prev
       LEFT OUTER JOIN (
         SELECT distinct(%(dest)s_organization_id)
           FROM saas_transaction
           WHERE created_at >= '%(period_start)s'
         AND created_at < '%(period_end)s'
         AND %(orig)s_organization_id = '%(organization_id)s'
         AND %(orig)s_account = '%(account)s') curr
         ON prev.%(dest)s_organization_id = curr.%(dest)s_organization_id
       WHERE prev.created_at >= '%(prev_period_start)s'
         AND prev.created_at < '%(prev_period_end)s'
         AND prev.%(orig)s_organization_id = '%(organization_id)s'
         AND prev.%(orig)s_account = '%(account)s'
         AND curr.%(dest)s_organization_id IS NULL""" % {
                "orig": orig, "dest": dest,
                "prev_period_start": prev_period_start,
                "prev_period_end": prev_period_end,
                "period_start": period_start,
                "period_end": period_end,
                "organization_id": organization.id,
                "account": account}, router.db_for_read(Transaction))
        churn_customer, churn_receivable = iter(churn_query).next()
        # A bit ugly but it does the job ...
        if orig == 'orig':
            kwargs = {'orig_organization': organization,
                      'orig_account': account}
        else:
            kwargs = {'dest_organization': organization,
                      'dest_account': account}
        query_result = Transaction.objects.filter(
            created_at__gte=period_start,
            created_at__lt=period_end, **kwargs).aggregate(
            Count('%s_organization' % dest, distinct=True),
            Sum('%s_amount' % dest))
        customer = query_result['%s_organization__count' % dest]
        receivable = query_result['%s_amount__sum' % dest]
        new_query = RawQuery(
"""SELECT count(distinct(curr.%(dest)s_organization_id)),
          SUM(curr.%(dest)s_amount)
   FROM saas_transaction curr
       LEFT OUTER JOIN (
         SELECT distinct(%(dest)s_organization_id)
           FROM saas_transaction
           WHERE created_at >= '%(prev_period_start)s'
         AND created_at < '%(prev_period_end)s'
         AND %(orig)s_organization_id = '%(organization_id)s'
         AND %(orig)s_account = '%(account)s') prev
         ON curr.%(dest)s_organization_id = prev.%(dest)s_organization_id
       WHERE curr.created_at >= '%(period_start)s'
         AND curr.created_at < '%(period_end)s'
         AND curr.%(orig)s_organization_id = '%(organization_id)s'
         AND curr.%(orig)s_account = '%(account)s'
         AND prev.%(dest)s_organization_id IS NULL""" % {
                "orig": orig, "dest": dest,
                "prev_period_start": prev_period_start,
                "prev_period_end": prev_period_end,
                "period_start": period_start,
                "period_end": period_end,
                "organization_id": organization.id,
                "account": account}, router.db_for_read(Transaction))
        new_customer, new_receivable = iter(new_query).next()
        period = period_end
        churn_customers += [(period, churn_customer)]
        churn_receivables += [(period, int(churn_receivable or 0))]
        customers += [(period, customer)]
        receivables += [(period, int(receivable or 0))]
        new_customers += [(period, new_customer)]
        new_receivables += [(period, int(new_receivable or 0))]
        trail_period_start = period_start
        period_start = period_end
    return ((churn_customers, customers, new_customers),
            (churn_receivables, receivables, new_receivables))


def aggregate_monthly_transactions(organization, account,
    account_title=None, from_date=None, orig='orig', dest='dest'):
    """
    12 months of total/new/churn into or out of (see *reverse*) *account*
    and associated distinct customers as extracted from Transactions.
    """
    #pylint: disable=too-many-locals,too-many-arguments
    if not account_title:
        account_title = str(account)
    interval = organization.natural_interval
    customers, account_totals = aggregate_monthly_churn(organization, account,
        interval, from_date=from_date, orig=orig, dest=dest)
    churned_custs, total_custs, new_custs = customers
    churned_account, total_account, new_account = account_totals
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
    account_table = [{"key": "Total %s" % account_title,
                     "values": total_account
                     },
                    {"key": "New %s" % account_title,
                     "values": new_account
                     },
                    {"key": "Churned %s" % account_title,
                     "values": churned_account
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
    return account_table, customer_table, customer_extra


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


def monthly_balances(organization=None, account=None, like_account=None,
                     until=None):
    values = []
    for end_period in month_periods(from_date=until):
        balance = Transaction.objects.get_balance(organization=organization,
            account=account, like_account=like_account, ends_at=end_period)
        values.append([end_period, abs(balance['amount'])])
    return values


def quaterly_balances(organization=None, account=None, like_account=None,
                     until=None):
    values = []
    for end_period in month_periods(from_date=until, step_months=3):
        balance = Transaction.objects.get_balance(organization=organization,
            account=account, like_account=like_account, ends_at=end_period)
        values.append([end_period, abs(balance['amount'])])
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
