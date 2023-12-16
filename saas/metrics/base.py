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

from datetime import datetime
import logging

from dateutil.relativedelta import relativedelta
from django.db import router
from django.db.models import Count, Sum
from django.db.models.sql.query import RawQuery

from .. import humanize
from ..compat import six
from ..models import Plan, Transaction
from ..utils import datetime_or_now, parse_tz

LOGGER = logging.getLogger(__name__)


def localize_time(time_to_convert, target_timezone, original_timezone):
    if target_timezone:
        # adding timezone info
        # + accounting for DST
        return target_timezone.localize(time_to_convert)
    return time_to_convert.replace(tzinfo=original_timezone)


def month_periods(nb_months=12, from_date=None, step_months=1,
                  tzinfo=None):
    """
    Constructs a list of (nb_months + 1) dates in the past that fall
    on the first of each month, defined as midnight in timezone *tz*,
    until *from_date* which is the last entry of the list returned.

    When *tz* is ``None``, the first of the month is defined
    as midnight UTC.

    Example::

        ["2017-05-01T07:00:00Z",
         "2017-06-01T07:00:00Z",
         "2017-07-01T07:00:00Z",
         "2017-08-01T07:00:00Z",
         "2017-09-01T07:00:00Z",
         "2017-10-01T07:00:00Z",
         "2017-11-01T07:00:00Z",
         "2017-12-01T08:00:00Z",
         "2018-01-01T08:00:00Z",
         "2018-02-01T08:00:00Z",
         "2018-03-01T08:00:00Z",
         "2018-03-26T07:11:24Z"]
    """
    #pylint:disable=invalid-name

    dates = []
    from_date = datetime_or_now(from_date)
    orig_tz = from_date.tzinfo
    tz_ob = parse_tz(tzinfo)
    if tz_ob:
        from_date = from_date.astimezone(tz_ob)
    dates.append(from_date)
    last = localize_time(
        datetime(day=from_date.day, month=from_date.month, year=from_date.year),
        tz_ob, orig_tz)
    if last.day != 1:
        last = localize_time(
            datetime(day=1, month=last.month, year=last.year),
            tz_ob, orig_tz)
        dates.append(last)
        nb_months = nb_months - 1
    for _ in range(0, nb_months, step_months):
        year = last.year
        month = last.month - step_months
        if month < 1:
            # integer division
            year = last.year + month // 12
            assert isinstance(year, six.integer_types)
            if month % 12 == 0:
                year -= 1
                month = 12
            else:
                month = month % 12
        last = datetime(day=1, month=month, year=year)
        last = localize_time(last, tz_ob, orig_tz)
        dates.append(last)
    dates.reverse()

    return dates


def set_to_start_of_period(date, time_unit):
    # Define common time attributes to reset
    common_replacements = {"minute": 0, "second": 0, "microsecond": 0}

    # Reset attributes based on time_unit
    if time_unit == humanize.HOURLY:
        date = date.replace(**common_replacements)
    elif time_unit == humanize.DAILY:
        date = date.replace(hour=0, **common_replacements)
    elif time_unit == humanize.WEEKLY:
        date = date - relativedelta(days=date.weekday())
        date = date.replace(hour=0, **common_replacements)
    elif time_unit == humanize.MONTHLY:
        date = date.replace(day=1, hour=0, **common_replacements)
    elif time_unit == humanize.YEARLY:
        date = date.replace(day=1, month=1, hour=0, **common_replacements)
    return date


def _generate_periods(time_unit, num_units, start_date, step_units,
                      timezone_str, include_start_date=True):
    #pylint:disable=too-many-arguments,too-many-locals
    period_dates = []
    start_date = datetime_or_now(start_date)
    original_timezone = start_date.tzinfo

    target_timezone = parse_tz(timezone_str)
    if target_timezone:
        start_date = start_date.astimezone(target_timezone)

    # Create a naive version of start_date
    start_date_naive = start_date.replace(tzinfo=None)

    # Check if start_date_naive is the start of a time period
    is_start_date_first_of_period = start_date_naive == set_to_start_of_period(
        start_date_naive, time_unit)

    # Include the unaltered start_date if applicable
    if include_start_date and not is_start_date_first_of_period:
        current_time = localize_time(
            start_date_naive, target_timezone, original_timezone)
        period_dates.append(current_time)

    # Adjust num_units based on include_start_date
    if not include_start_date:
        num_units += 1
    if is_start_date_first_of_period and include_start_date:
        num_units += 1

    # Generate period dates
    for i in range(num_units):
        time_unit_str = humanize.describe_period_name(time_unit, 2)
        delta_args = {time_unit_str: -i * step_units}
        next_date = start_date_naive + relativedelta(**delta_args)

        datetime_object = set_to_start_of_period(next_date, time_unit)
        last_date = localize_time(
            datetime_object, target_timezone, original_timezone)

        period_dates.append(last_date)

    return list(reversed(period_dates))


def generate_periods(period, nb_periods=0, from_date=None, step_units=1,
                     tzinfo=None, include_start_date=True):
    #pylint:disable=too-many-arguments
    assert period in (humanize.HOURLY, humanize.DAILY, humanize.WEEKLY,
        humanize.MONTHLY, humanize.YEARLY)
    if not nb_periods:
        if period == humanize.HOURLY:
            nb_periods = 24
        elif period == humanize.DAILY:
            nb_periods = 7
        elif period == humanize.WEEKLY:
            nb_periods = 8
        elif period == humanize.MONTHLY:
            nb_periods = 12
        elif period == humanize.YEARLY:
            nb_periods = 5
    return _generate_periods(period, nb_periods, from_date, step_units, tzinfo,
        include_start_date=include_start_date)


def aggregate_transactions_by_period(organization, account, date_periods,
                      orig='orig', dest='dest', **kwargs):
    # pylint: disable=too-many-locals,too-many-arguments,invalid-name
    counts = []
    amounts = []
    period_start = date_periods[0]
    unit = None
    for period_end in date_periods[1:]:
        # A bit ugly but it does the job ...
        kwargs.update({'%s_organization' % orig: organization,
            '%s_account' % orig: account})

        count, amount, _unit = 0, 0, None
        query_result = Transaction.objects.filter(
            created_at__gte=period_start,
            created_at__lt=period_end, **kwargs).values(
                '%s_unit' % dest).annotate(
                    count=Count('%s_organization' % dest, distinct=True),
                    sum=Sum('%s_amount' % dest))
        if query_result:
            count = query_result[0]['count']
            amount = query_result[0]['sum']
            _unit = query_result[0]['%s_unit' % dest]
            if _unit:
                unit = _unit
        period = period_end
        counts += [(period, count)]
        amounts += [(period, int(amount or 0))]
        period_start = period_end

    return (counts, amounts, unit)


def _aggregate_transactions_change_by_period(organization, account,
                            date_periods, orig='orig', dest='dest'):
    """
    Returns a table of records over *date_periods*.
    """
    #pylint:disable=too-many-locals,too-many-arguments,too-many-statements
    #pylint:disable=invalid-name
    customers = []
    receivables = []
    new_customers = []
    new_receivables = []
    churn_customers = []
    churn_receivables = []
    unit = None
    period_start = date_periods[0]
    for period_end in date_periods[1:]:
        delta = Plan.get_natural_period(1, organization.natural_interval)
        prev_period_end = period_end - delta
        prev_period_start = prev_period_end - relativedelta(
            period_end, period_start)
        LOGGER.debug(
            "computes churn between periods ['%s', '%s'] and ['%s', '%s']",
            prev_period_start.isoformat(), prev_period_end.isoformat(),
            period_start.isoformat(), period_end.isoformat())
        try:
            churn_query = RawQuery(
    """SELECT COUNT(DISTINCT(prev.%(dest)s_organization_id)),
              SUM(prev.%(dest)s_amount),
              prev.%(dest)s_unit
           FROM saas_transaction prev
           LEFT OUTER JOIN (
             SELECT distinct(%(dest)s_organization_id), %(orig)s_unit
               FROM saas_transaction
               WHERE created_at >= '%(period_start)s'
             AND created_at < '%(period_end)s'
             AND %(orig)s_organization_id = '%(organization_id)s'
             AND %(orig)s_account = '%(account)s'
             ) curr
             ON prev.%(dest)s_organization_id = curr.%(dest)s_organization_id
           WHERE prev.created_at >= '%(prev_period_start)s'
             AND prev.created_at < '%(prev_period_end)s'
             AND prev.%(orig)s_organization_id = '%(organization_id)s'
             AND prev.%(orig)s_account = '%(account)s'
             AND curr.%(dest)s_organization_id IS NULL
             GROUP BY prev.%(dest)s_unit
             """ % {
                    "orig": orig, "dest": dest,
                    "prev_period_start": prev_period_start,
                    "prev_period_end": prev_period_end,
                    "period_start": period_start,
                    "period_end": period_end,
                    "organization_id": organization.id,
                    "account": account}, router.db_for_read(Transaction))
            churn_customer, churn_receivable, churn_receivable_unit = next(
                iter(churn_query))
            if churn_receivable_unit:
                unit = churn_receivable_unit
        except StopIteration:
            churn_customer, churn_receivable, churn_receivable_unit = 0, 0, None

        # A bit ugly but it does the job ...
        if orig == 'orig':
            kwargs = {'orig_organization': organization,
                      'orig_account': account}
        else:
            kwargs = {'dest_organization': organization,
                      'dest_account': account}

        customer = 0
        receivable = 0
        receivable_unit = None
        query_result = Transaction.objects.filter(
            created_at__gte=period_start,
            created_at__lt=period_end, **kwargs).values(
                '%s_unit' % dest).annotate(
                    count=Count('%s_organization' % dest, distinct=True),
                    sum=Sum('%s_amount' % dest))
        if query_result:
            customer = query_result[0]['count']
            receivable = query_result[0]['sum']
            receivable_unit = query_result[0]['%s_unit' % dest]
            if receivable_unit:
                unit = receivable_unit

        try:
            new_query = RawQuery(
    """SELECT count(distinct(curr.%(dest)s_organization_id)),
              SUM(curr.%(dest)s_amount),
              curr.%(dest)s_unit
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
             AND prev.%(dest)s_organization_id IS NULL
             GROUP BY curr.%(dest)s_unit""" % {
                    "orig": orig, "dest": dest,
                    "prev_period_start": prev_period_start,
                    "prev_period_end": prev_period_end,
                    "period_start": period_start,
                    "period_end": period_end,
                    "organization_id": organization.id,
                    "account": account}, router.db_for_read(Transaction))
            new_customer, new_receivable, new_receivable_unit = next(
                iter(new_query))
            if new_receivable_unit:
                unit = new_receivable_unit
        except StopIteration:
            new_customer, new_receivable, new_receivable_unit = 0, 0, None

        units = get_different_units(churn_receivable_unit,
            receivable_unit, new_receivable_unit)
        if len(units) > 1:
            LOGGER.error(
              "different units in _aggregate_transactions_change_by_period: %s",
                units)

        period = period_end
        churn_customers += [(period, churn_customer)]
        churn_receivables += [(period, int(churn_receivable or 0))]
        customers += [(period, customer)]
        receivables += [(period, int(receivable or 0))]
        new_customers += [(period, new_customer)]
        new_receivables += [(period, int(new_receivable or 0))]
        period_start = period_end

    return ((churn_customers, customers, new_customers),
            (churn_receivables, receivables, new_receivables), unit)


def aggregate_transactions_change_by_period(organization, account, date_periods,
    account_title=None, orig='orig', dest='dest'):
    """
    12 months of total/new/churn into or out of (see *reverse*) *account*
    and associated distinct customers as extracted from Transactions.
    """
    #pylint: disable=too-many-locals,too-many-arguments,invalid-name
    if not account_title:
        account_title = str(account)
    customers, account_totals, unit = _aggregate_transactions_change_by_period(
        organization, account, date_periods=date_periods, orig=orig, dest=dest)
    churned_custs, total_custs, new_custs = customers
    churned_account, total_account, new_account = account_totals
    net_new_custs = []
    cust_churn_percent = []
    last_nb_total_custs = 0
    for index in range(0, len(date_periods) - 1):
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
    account_table = [{
        'slug': "Total %s" % account_title,
        'title': "Total %s" % account_title,
        'values': total_account
    }, {
        'slug': "New %s" % account_title,
        'title': "New %s" % account_title,
        'values': new_account
    }, {
        'slug': "Churned %s" % account_title,
        'title': "Churned %s" % account_title,
        'values': churned_account
    }]
    customer_table = [{
        'slug': "total-customers",
        'title': "Total # of Customers",
        'values': total_custs
    }, {
        'slug': "new-customers",
        'title': "# of new Customers",
        'values': new_custs
    }, {
        'slug': "churned-customers",
        'title': "# of churned Customers",
        'values': churned_custs
    }, {
        'slug': "net-new-customers",
        'title': "Net New Customers",
        'values': net_new_custs
    }]
    customer_extra = [{
        'slug': "percent-customer-churn",
        'title': "% Customer Churn",
        'values': cust_churn_percent
    }]
    return account_table, customer_table, customer_extra, unit


def abs_balances_by_period(organization=None, account=None, like_account=None,
                           date_periods=None):
    if date_periods is None:
        date_periods = []

    balances, unit = balances_by_period(
        organization=organization, account=account,
        like_account=like_account, date_periods=date_periods)
    return [(item[0], abs(item[1])) for item in balances], unit


def balances_by_period(organization=None, account=None, like_account=None,
                       date_periods=None):
    values = []
    unit = None
    for end_period in date_periods:
        balance = Transaction.objects.get_balance(organization=organization,
            account=account, like_account=like_account, ends_at=end_period)
        values.append([end_period, balance['amount']])
        _unit = balance.get('unit')
        if _unit:
            unit = _unit

    return values, unit


def get_different_units(*args):
    # removing None and duplicate values
    units = {_unit for _unit in args if _unit is not None}
    return list(units)
