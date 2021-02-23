# Copyright (c) 2021, DjaoDjin inc.
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
        parser.add_argument('--provider', action='append',
            dest='providers', default=None,
            help='Specifies provider to generate reports for.')

    @staticmethod
    def construct_date_periods(at_time, timezone=None):
        # discarding time, keeping utc tzinfo (00:00:00 utc)
        today = at_time.replace(hour=0, minute=0, second=0, microsecond=0)
        tzinfo = parse_tz(timezone)
        if tzinfo:
            # we are interested in 00:00 local time, if we don't have
            # local time zone, fall back to 00:00 utc time
            # in case we have local timezone, replace utc with it
            today = tzinfo.localize(today.replace(tzinfo=None))
        if today.weekday() == SU:
            last_sunday = today
        else:
            last_sunday = today + relativedelta(weeks=-1, weekday=SU)
        prev_sunday = last_sunday - relativedelta(weeks=1)

        prev_year = [
            last_sunday + relativedelta(years=-1, weeks=-1, weekday=SU),
            last_sunday + relativedelta(years=-1, weekday=SU)
        ]
        prev_week = [      # 2 consecutive weeks (last and previous)
            prev_sunday - relativedelta(weeks=1),
            prev_sunday,
            last_sunday
        ]
        return prev_week, prev_year

    @staticmethod
    def construct_table(table, unit):
        for row in table:
            val = row['values']
            try:
                amount = (val['last'] - val['prev']) * 100 / val['prev']
                prev = str(round(amount, 2)) + '%'
                if amount > 0:
                    prev = '+' + prev
            except ZeroDivisionError:
                prev = 'N/A'
            try:
                amount = \
                    (val['last'] - val['prev_year']) * 100 / val['prev_year']
                prev_year = str(round(amount, 2)) + '%'
                if amount > 0:
                    prev_year = '+' + prev_year
            except ZeroDivisionError:
                prev_year = 'N/A'
            val['last'] = as_money(val['last'], unit)
            val['prev'] = prev
            val['prev_year'] = prev_year
        return table

    @staticmethod
    def get_weekly_perf_data(provider, prev_week, prev_year):
        #pylint:disable=too-many-locals
        account_table, _, _, table_unit = \
            aggregate_transactions_change_by_period(provider,
                Transaction.RECEIVABLE, account_title='Sales',
                orig='orig', dest='dest',
                date_periods=prev_week)
        account_table_prev_year, _, _, _ = \
            aggregate_transactions_change_by_period(provider,
                Transaction.RECEIVABLE, account_title='Sales',
                orig='orig', dest='dest',
                date_periods=prev_year)

        _, payment_amounts, payments_unit = \
            aggregate_transactions_by_period(
                provider, Transaction.RECEIVABLE,
                orig='dest', dest='dest',
                orig_account=Transaction.BACKLOG,
                orig_organization=provider,
                date_periods=prev_week)
        _, payment_amounts_prev_year, _ = \
            aggregate_transactions_by_period(
                provider, Transaction.RECEIVABLE,
                orig='dest', dest='dest',
                orig_account=Transaction.BACKLOG,
                orig_organization=provider,
                date_periods=prev_year)

        _, refund_amounts, refund_unit = \
            aggregate_transactions_by_period(
                provider, Transaction.REFUND,
                orig='dest', dest='dest',
                date_periods=prev_week)
        _, refund_amounts_prev_year, _ = \
            aggregate_transactions_by_period(
                provider, Transaction.REFUND,
                orig='dest', dest='dest',
                date_periods=prev_year)

        unit = settings.DEFAULT_UNIT

        units = get_different_units(table_unit, payments_unit, refund_unit)

        if len(units) > 1:
            LOGGER.error("different units in get_weekly_perf_data: %s", units)

        if units:
            unit = units[0]

        table = [
            {'key': "Total Sales",
             'values': {
                'last': account_table[0]['values'][1][1],
                'prev': account_table[0]['values'][0][1],
                'prev_year': account_table_prev_year[0]['values'][0][1]
            }},
            {'key': "New Sales",
             'values': {
                'last': account_table[1]['values'][1][1],
                'prev': account_table[1]['values'][0][1],
                'prev_year': account_table_prev_year[1]['values'][0][1]
            }},
            {'key': "Churned Sales",
             'values': {
                 'last': account_table[2]['values'][1][1],
                'prev': account_table[2]['values'][0][1],
                'prev_year': account_table_prev_year[2]['values'][0][1]
            }},
            {'key': "Payments",
             'values': {
                 'last': payment_amounts[1][1],
                 'prev': payment_amounts[0][1],
                 'prev_year': payment_amounts_prev_year[0][1]
            }},
            {'key': "Refunds",
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
        self.stdout.write("running report_weekly_revenue at %s" % at_time)

        providers = get_organization_model().objects.filter(is_provider=True)
        provider_slugs = options.get('providers')
        if provider_slugs:
            providers = providers.filter(slug__in=provider_slugs)
        for provider in providers:
            dates = self.construct_date_periods(
                at_time, timezone=provider.default_timezone)
            prev_week, prev_year = dates
            self.stdout.write("Two last consecutive weeks:\n  %s %s %s" % (
                prev_week[0].isoformat(), prev_week[1].isoformat(),
                prev_week[2].isoformat()))
            self.stdout.write("Same week last year:\n"\
                "                            %s %s" % (
                prev_year[0].isoformat(), prev_year[1].isoformat()))
            data, unit = self.get_weekly_perf_data(
                provider, prev_week, prev_year)
            table = self.construct_table(data, unit)
            signals.weekly_sales_report_created.send(sender=__name__,
                provider=provider, dates=dates, data=table)
