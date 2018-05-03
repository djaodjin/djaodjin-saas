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

from ...managers.metrics import (aggregate_within_periods,
    aggregate_monthly_transactions)
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
        last_week = [last_sunday - relativedelta(weeks=1), last_sunday]
        week_before = [last_week[0] - relativedelta(weeks=1), last_week[0]]
        week_last_year =  [last_sunday - relativedelta(years=1, weeks=1), last_sunday - relativedelta(years=1)]
        periods = [last_week, week_before, week_last_year]

        #account_table, _, _ = \
        #    aggregate_monthly_transactions(self.provider,
        #        Transaction.RECEIVABLE, account_title='Sales',
        #        orig='orig', dest='dest',
        #        from_date=self.ends_at, tz=self.timezone)

        _, payment_amounts = aggregate_within_periods(
            provider, Transaction.RECEIVABLE,
            orig='dest', dest='dest',
            orig_account=Transaction.BACKLOG,
            orig_organization=provider,
            periods=periods)

        _, refund_amounts = aggregate_within_periods(
            provider, Transaction.REFUND,
            orig='dest', dest='dest',
            periods=periods)

        #import pdb; pdb.set_trace()

        #account_table += [
        #    {"key": "Payments", "values": payment_amounts},
        #    {"key": "Refunds", "values": refund_amounts}]