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

"""Command for the cron job. Send revenue report for the last week"""

import logging

from dateutil.relativedelta import relativedelta, SU
from django.core.management.base import BaseCommand

from ... import settings
from ... import signals
from ...humanize import as_money
from ...metrics.base import (aggregate_transactions_by_period,
                             aggregate_transactions_change_by_period, get_different_units)
from ...models import Transaction
from ...utils import datetime_or_now, get_organization_model, parse_tz

LOGGER = logging.getLogger(__name__)

class Command(BaseCommand):
    """Send past week revenue report in email"""
    help = 'Send past week revenue report in email'

    def add_arguments(self, parser):
        parser.add_argument(
            '--at-time', action='store',
            dest='at_time', default=None,
            help='Specifies the time at which the command runs'
        )
        parser.add_argument(
            '--provider', action='append',
            dest='providers', default=None,
            help='Specifies provider to generate reports for.'
        )
        parser.add_argument(
            '--period', action='store',
            dest='period', default='weekly',
            choices=['hourly', 'daily', 'weekly', 'monthly', 'yearly'],
            help='Specifies the period to generate reports for'
        )

    @staticmethod
    def construct_date_periods(at_time, period='weekly', timezone=None):
        # discarding time, keeping utc tzinfo (00:00:00 utc)
        tzinfo = parse_tz(timezone)

        def localize_time(time):
            # we are interested in 00:00 local time, if we don't have
            # local time zone, fall back to 00:00 utc time
            # in case we have local timezone, replace utc with it
            return tzinfo.localize(time.replace(tzinfo=None)) if tzinfo else time

        base_time = at_time.replace(minute=0, second=0, microsecond=0)
        current_time = localize_time(at_time)

        normalization_rules = {
            'daily': {'hour': 0},
            'weekly': {'hour': 0},
            'monthly': {'day': 1, 'hour': 0},
            'yearly': {'month': 1, 'day': 1, 'hour': 0},
        }
        base_time = localize_time(base_time)
        base_time = base_time.replace(**normalization_rules.get(period, {}))

        prev_period, prev_year = None, None
        if period == 'weekly':
            last_sunday = base_time if base_time.weekday() == SU else (base_time
                                                                       + relativedelta(weeks=-1, weekday=SU))
            prev_sunday = last_sunday - relativedelta(weeks=1)
            prev_period = [prev_sunday - relativedelta(weeks=1),
                           prev_sunday,
                           last_sunday]
            prev_year = [last_sunday + relativedelta(years=-1, weeks=-1, weekday=SU),
                         last_sunday + relativedelta(years=-1, weekday=SU)]
        elif period == 'yearly':
            # For 'yearly' period:
            # - 'prev_period' represents the time range starting from the first day of the previous year
            #   up to the current time. If today is the first day of the year, it starts from today.
            # - 'prev_year' represents the time range of the year before the 'prev_period'.
            #
            # For example, if today's date is 2023-09-06:
            # - 'prev_period' would be [2022-01-01, 2023-01-01, 2023-09-06]
            # - 'prev_year' would be [2021-01-01, 2022-01-01]
            first_of_year = base_time if (base_time.month, base_time.day) == (1, 1) else (
                base_time.replace(month=1, day=1))
            prev_year_start = first_of_year - relativedelta(years=1)
            prev_period = [prev_year_start,
                           first_of_year,
                           current_time]
            prev_year = [prev_year_start - relativedelta(years=1),
                         prev_year_start]
        elif period == 'monthly':
            first_day_of_month = base_time if base_time.day == 1 else (
                    base_time + relativedelta(months=-1, day=1))
            prev_month = first_day_of_month - relativedelta(months=1)
            prev_period = [prev_month - relativedelta(months=1),
                           prev_month,
                           first_day_of_month]
            prev_year = [prev_month - relativedelta(years=1, months=1),
                         prev_month - relativedelta(years=1)]
        elif period == 'daily':
            first_hour_of_day = base_time if base_time.hour == 0 else (
                    base_time + relativedelta(days=-1, hour=0)
            )
            prev_day = first_hour_of_day - relativedelta(days=1)
            prev_period = [prev_day - relativedelta(days=1),
                           prev_day,
                           first_hour_of_day]
            prev_year = [first_hour_of_day - relativedelta(years=1, days=1),
                         first_hour_of_day - relativedelta(years=1)]
        elif period == 'hourly':
            first_min_of_hour = base_time if base_time.minute == 0 else (
                    base_time + relativedelta(hours=-1))
            prev_hour = first_min_of_hour - relativedelta(hours=1)
            prev_period = [prev_hour - relativedelta(hours=1),
                           prev_hour,
                           first_min_of_hour]
            prev_year = [first_min_of_hour - relativedelta(years=1, hours=1),
                         first_min_of_hour - relativedelta(years=1)]

        if period not in ['hourly', 'daily', 'weekly', 'monthly', 'yearly']:
            return None, None

        return prev_period, prev_year

    @staticmethod
    def construct_table(table, unit):
        def calculate_percentage_change(current, previous):
            try:
                amount = (current - previous) * 100 / previous
                percentage = str(round(amount, 2)) + '%'
                if amount > 0:
                    percentage = '+' + percentage
                return percentage
            except ZeroDivisionError:
                return 'N/A'

        for row in table:
            val = row['values']
            val['prev'] = calculate_percentage_change(val['last'], val['prev'])
            val['prev_year'] = calculate_percentage_change(val['last'], val['prev_year'])
            val['last'] = as_money(val['last'], unit)
        return table

    @staticmethod
    def get_perf_data(provider, prev_periods, prev_year_periods, period_type):
        # pylint:disable=too-many-locals
        account_table, _, _, table_unit = aggregate_transactions_change_by_period(
            provider, Transaction.RECEIVABLE, account_title='Sales',
            orig='orig', dest='dest', date_periods=prev_periods
        )
        account_table_prev_year, _, _, _ = aggregate_transactions_change_by_period(
            provider, Transaction.RECEIVABLE, account_title='Sales',
            orig='orig', dest='dest', date_periods=prev_year_periods
        )

        _, payment_amounts, payments_unit = aggregate_transactions_by_period(
            provider, Transaction.RECEIVABLE,
            orig='dest', dest='dest', orig_account=Transaction.BACKLOG,
            orig_organization=provider, date_periods=prev_periods
        )
        _, payment_amounts_prev_year, _ = aggregate_transactions_by_period(
            provider, Transaction.RECEIVABLE,
            orig='dest', dest='dest', orig_account=Transaction.BACKLOG,
            orig_organization=provider, date_periods=prev_year_periods
        )

        _, refund_amounts, refund_unit = aggregate_transactions_by_period(
            provider, Transaction.REFUND,
            orig='dest', dest='dest', date_periods=prev_periods
        )
        _, refund_amounts_prev_year, _ = aggregate_transactions_by_period(
            provider, Transaction.REFUND,
            orig='dest', dest='dest', date_periods=prev_year_periods
        )

        unit = settings.DEFAULT_UNIT
        units = get_different_units(table_unit, payments_unit, refund_unit)

        if len(units) > 1:
            LOGGER.error("different units in get_%s_perf_data: %s", period_type, units)

        if units:
            unit = units[0]
        table = [{
            'slug': "Total Sales",
            'title': "Total Sales",
            'values': {
                'last': account_table[0]['values'][1][1],
                'prev': account_table[0]['values'][0][1],
                'prev_year': account_table_prev_year[0]['values'][0][1]
            }}, {
            'slug': "New Sales",
            'title': "New Sales",
            'values': {
                'last': account_table[1]['values'][1][1],
                'prev': account_table[1]['values'][0][1],
                'prev_year': account_table_prev_year[1]['values'][0][1]
            }}, {
            'slug': "Churned Sales",
            'title': "Churned Sales",
            'values': {
                'last': account_table[2]['values'][1][1],
                'prev': account_table[2]['values'][0][1],
                'prev_year': account_table_prev_year[2]['values'][0][1]
            }}, {
            'slug': "Payments",
            'title': "Payments",
            'values': {
                'last': payment_amounts[1][1],
                'prev': payment_amounts[0][1],
                'prev_year': payment_amounts_prev_year[0][1]
            }}, {
            'slug': "Refunds",
            'title': "Refunds",
            'values': {
                'last': refund_amounts[1][1],
                'prev': refund_amounts[0][1],
                'prev_year': refund_amounts_prev_year[0][1]
            }}
        ]
        return (table, unit)

    def handle(self, *args, **options):
        # aware utc datetime object
        at_time = datetime_or_now(options.get('at_time'))
        period = options.get('period', 'weekly')

        self.stdout.write("running report_weekly_revenue for %s %s period at %s" %
                          ('an' if period == 'hourly' else 'a', period, at_time))

        providers = get_organization_model().objects.filter(is_provider=True)
        provider_slugs = options.get('providers')
        if provider_slugs:
            providers = providers.filter(slug__in=provider_slugs)
        for provider in providers:
            dates = self.construct_date_periods(
                at_time, period=period, timezone=provider.default_timezone)
            prev_period, prev_year = dates
            if period == 'yearly':
                self.stdout.write(
                    "Two last consecutive yearly periods\n: %s to %s and %s to %s" %
                    (prev_period[0].isoformat(), prev_period[1].isoformat(), prev_period[1].isoformat(),
                     prev_period[2].isoformat())
                )
                self.stdout.write(
                    "Year before the corresponding yearly period\n: %s to %s" %
                    (prev_year[0].isoformat(), prev_year[1].isoformat())
                )
            else:
                self.stdout.write(
                    "Two last consecutive %s periods\n: %s to %s and %s to %s" %
                    (period, prev_period[0].isoformat(), prev_period[1].isoformat(),
                     prev_period[1].isoformat(), prev_period[2].isoformat())
                )
                self.stdout.write(
                    "Same %s period from the previous year\n: %s to %s" %
                    (period, prev_year[0].isoformat(), prev_year[1].isoformat())
                )
            data, unit = self.get_perf_data(provider, prev_period, prev_year, period_type=period)
            table = self.construct_table(data, unit)
            signals.weekly_sales_report_created.send(sender=__name__, provider=provider, dates=dates, data=table)
