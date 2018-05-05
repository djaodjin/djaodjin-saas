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

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta, SU

from django.core.management.base import BaseCommand
from django.utils.timezone import utc

from ...managers.metrics import (aggregate_transactions_by_period,
    aggregate_transactions_change_by_period)
from ...models import Organization, Transaction

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

    def handle(self, *args, **options):
        provider_slug = options.get('provider')
        providers = Organization.objects.filter(is_provider=True)
        if provider_slug:
            providers = providers.filter(slug=provider_slug)
        provider = providers[0]

        today_dt = datetime.today()
        today = datetime(
            year=today_dt.year,
            month=today_dt.month,
            day=today_dt.day,
            tzinfo=utc
        )
        last_sunday = today + relativedelta(weeks=-1, weekday=SU(0))
        prev_sunday = last_sunday - relativedelta(weeks=1)
        prev_year = [last_sunday - relativedelta(years=1, weeks=1), last_sunday - relativedelta(years=1)]
        prev_week = [prev_sunday - relativedelta(weeks=1), prev_sunday, last_sunday]

        account_table, _, _ = \
            aggregate_transactions_change_by_period(provider,
                Transaction.RECEIVABLE, account_title='Sales',
                orig='orig', dest='dest',
                date_periods=prev_week)

        account_table_prev_year, _, _ = \
            aggregate_transactions_change_by_period(provider,
                Transaction.RECEIVABLE, account_title='Sales',
                orig='orig', dest='dest',
                date_periods=prev_year)

        _, payment_amounts = aggregate_transactions_by_period(
            provider, Transaction.RECEIVABLE,
            orig='dest', dest='dest',
            orig_account=Transaction.BACKLOG,
            orig_organization=provider,
            date_periods=prev_week)

        _, payment_amounts_prev_year = aggregate_transactions_by_period(
            provider, Transaction.RECEIVABLE,
            orig='dest', dest='dest',
            orig_account=Transaction.BACKLOG,
            orig_organization=provider,
            date_periods=prev_year)

        _, refund_amounts = aggregate_transactions_by_period(
            provider, Transaction.REFUND,
            orig='dest', dest='dest',
            date_periods=prev_week)

        _, refund_amounts_prev_year = aggregate_transactions_by_period(
            provider, Transaction.REFUND,
            orig='dest', dest='dest',
            date_periods=prev_year)

        account_table += [
            {"key": "Payments", "values": payment_amounts},
            {"key": "Refunds", "values": refund_amounts}]
        import pdb; pdb.set_trace()
