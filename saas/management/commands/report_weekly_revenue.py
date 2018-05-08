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
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta, SU

from django.core.management.base import BaseCommand
from django.utils.timezone import utc
from django.core.mail import send_mail

from ...managers.metrics import (aggregate_transactions_by_period,
    aggregate_transactions_change_by_period)
from ...models import Organization, Transaction
from ...utils import datetime_or_now

class Command(BaseCommand):
    """Send past week revenue report in email"""
    help = 'Send past week revenue report in email'

    def add_arguments(self, parser):
        parser.add_argument(
            '--provider',
            action='store',
            dest='provider',
            help='Specify a provider to generate reports for',
        )

    def construct_date_periods(self):
        today_dt = datetime_or_now()
        today = datetime(
            year=today_dt.year,
            month=today_dt.month,
            day=today_dt.day,
            tzinfo=utc
        )
        last_sunday = today + relativedelta(weeks=-1, weekday=SU(0))
        prev_sunday = last_sunday - relativedelta(weeks=1)
        prev_year = [last_sunday - relativedelta(years=1, weeks=1),
                    last_sunday - relativedelta(years=1)]
        prev_week = [prev_sunday - relativedelta(weeks=1),
                    prev_sunday, last_sunday]
        return prev_week, prev_year

    def construct_table(self, data):
        table = {
            'total_sales': {
                'last': data['account_table'][0]['values'][1][1],
                'prev': data['account_table'][0]['values'][0][1],
                'prev_year': \
                    data['account_table_prev_year'][0]['values'][0][1]
            },
            'new_sales': {
                'last': data['account_table'][1]['values'][1][1],
                'prev': data['account_table'][1]['values'][0][1],
                'prev_year': \
                    data['account_table_prev_year'][1]['values'][0][1]
            },
            'churned_sales': {
                'last': data['account_table'][2]['values'][1][1],
                'prev': data['account_table'][2]['values'][0][1],
                'prev_year': \
                    data['account_table_prev_year'][2]['values'][0][1]
            },
            'payments': {
                'last': data['payment_amounts'][1][1],
                'prev': data['payment_amounts'][0][1],
                'prev_year': data['payment_amounts_prev_year'][0][1]
            },
            'refunds': {
                'last': data['refund_amounts'][1][1],
                'prev': data['refund_amounts'][0][1],
                'prev_year': data['refund_amounts_prev_year'][0][1]
            },
        }

        for k, v in iteritems(table):
            try:
                amount = (v['last'] - v['prev']) * 100 / v['prev']
                prev = str(amount) + '%'
                if amount > 0:
                    prev = '+' + prev
            except ZeroDivisionError:
                prev = 'N/A'
            try:
                amount = \
                    (v['last'] - v['prev_year']) * 100 / v['prev_year']
                prev_year = str(amount) + '%'
                if amount > 0:
                    prev_year = '+' + prev_year
            except ZeroDivisionError:
                prev_year = 'N/A'

            v['last'] = '$' + str(v['last'])
            v['prev'] = prev
            v['prev_year'] = prev_year

        return table

    def get_company_weekly_perf_data(self, provider,
        prev_week, prev_year):

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

    def send_email(self, provider, table):
        from pprint import pprint
        pprint(table)
        message = 'a table should be here'
        to = ['knivets@gmail.com', provider.email]
        # send_mass_mail?
        send_mail(
            'Weekly Report',
            message,
            'from@example.com',
            to,
            fail_silently=False,
        )

    def handle(self, *args, **options):
        providers = Organization.objects.filter(is_provider=True)
        provider_slug = options.get('provider')
        if provider_slug:
            providers = providers.filter(slug=provider_slug)
        prev_week, prev_year = self.construct_date_periods()

        for provider in providers:
            data = self.get_company_weekly_perf_data(
                provider, prev_week, prev_year)
            table = self.construct_table(data)
            self.send_email(provider, table)
