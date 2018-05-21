# Copyright (c) 2018, DjaoDjin inc.
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

from six import iteritems
from collections import OrderedDict
from dateutil.relativedelta import relativedelta, SU
from django.core.management.base import BaseCommand

from ...managers.metrics import (aggregate_transactions_by_period,
    aggregate_transactions_change_by_period)
from ...models import Organization, Transaction
from ...utils import datetime_or_now, parse_tz
from ...humanize import as_money
from ... import signals

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
            '--provider',
            action='store',
            dest='provider',
            help='Specify a provider to generate reports for',
        )

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
        if today.weekday() == 0:
            last_sunday = today
        else:
            last_sunday = today + relativedelta(weeks=-1, weekday=SU(0))
        prev_sunday = last_sunday - relativedelta(weeks=1)
        prev_year = [last_sunday - relativedelta(years=1, weeks=1),
                    last_sunday - relativedelta(years=1)]
        prev_week = [prev_sunday - relativedelta(weeks=1),
                    prev_sunday, last_sunday]
        return prev_week, prev_year

    @staticmethod
    def construct_table(data):
        table = OrderedDict({
            'Total Sales': {
                'last': data['account_table'][0]['values'][1][1],
                'prev': data['account_table'][0]['values'][0][1],
                'prev_year': \
                    data['account_table_prev_year'][0]['values'][0][1]
            },
            'New Sales': {
                'last': data['account_table'][1]['values'][1][1],
                'prev': data['account_table'][1]['values'][0][1],
                'prev_year': \
                    data['account_table_prev_year'][1]['values'][0][1]
            },
            'Churned Sales': {
                'last': data['account_table'][2]['values'][1][1],
                'prev': data['account_table'][2]['values'][0][1],
                'prev_year': \
                    data['account_table_prev_year'][2]['values'][0][1]
            },
            'Payments': {
                'last': data['payment_amounts'][1][1],
                'prev': data['payment_amounts'][0][1],
                'prev_year': data['payment_amounts_prev_year'][0][1]
            },
            'Refunds': {
                'last': data['refund_amounts'][1][1],
                'prev': data['refund_amounts'][0][1],
                'prev_year': data['refund_amounts_prev_year'][0][1]
            },
        })

        for _, val in iteritems(table):
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

            val['last'] = as_money(val['last'])
            val['prev'] = prev
            val['prev_year'] = prev_year

        return table

    @staticmethod
    def get_company_weekly_perf_data(provider, prev_week, prev_year):
        data = {}

        data['account_table'], _, _ = \
            aggregate_transactions_change_by_period(provider,
                Transaction.RECEIVABLE, account_title='Sales',
                orig='orig', dest='dest',
                date_periods=prev_week)

        data['account_table_prev_year'], _, _ = \
            aggregate_transactions_change_by_period(provider,
                Transaction.RECEIVABLE, account_title='Sales',
                orig='orig', dest='dest',
                date_periods=prev_year)

        _, data['payment_amounts'] = aggregate_transactions_by_period(
            provider, Transaction.RECEIVABLE,
            orig='dest', dest='dest',
            orig_account=Transaction.BACKLOG,
            orig_organization=provider,
            date_periods=prev_week)

        _, data['payment_amounts_prev_year'] = \
            aggregate_transactions_by_period(
                provider, Transaction.RECEIVABLE,
                orig='dest', dest='dest',
                orig_account=Transaction.BACKLOG,
                orig_organization=provider,
                date_periods=prev_year)

        _, data['refund_amounts'] = aggregate_transactions_by_period(
            provider, Transaction.REFUND,
            orig='dest', dest='dest',
            date_periods=prev_week)

        _, data['refund_amounts_prev_year'] = \
            aggregate_transactions_by_period(
                provider, Transaction.REFUND,
                orig='dest', dest='dest',
                date_periods=prev_year)

        return data

    def handle(self, *args, **options):
        # aware utc datetime object
        today_dt = datetime_or_now(options.get('at_time'))
        self.stdout.write("running report_weekly_revenue at %s" % today_dt)

        providers = Organization.objects.filter(is_provider=True)
        provider_slug = options.get('provider')
        if provider_slug:
            providers = providers.filter(slug=provider_slug)

        for provider in providers:
            dates = self.construct_date_periods(
                today_dt, timezone=provider.default_timezone)
            prev_week, prev_year = dates
            data = self.get_company_weekly_perf_data(
                provider, prev_week, prev_year)
            table = self.construct_table(data)
            signals.weekly_sales_report_created.send(sender=__name__,
                provider=provider, dates=dates, data=table)
