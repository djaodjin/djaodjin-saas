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

"""Command for the cron job. Send revenue report for the last week"""

from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils.timezone import utc

from ...managers.metrics import (aggregate_monthly,
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
        today_date = datetime.today()
        today = datetime(
            year=today_date.year,
            month=today_date.month,
            day=today_date.day,
            tzinfo=utc
        )
        monday = today - timedelta(days=today.weekday())
        account_table, _, _ = \
            aggregate_monthly_transactions(provider,
                Transaction.RECEIVABLE, account_title='Sales',
                orig='orig', dest='dest',
                from_date=monday)

        _, payment_amounts = aggregate_monthly(
            provider, Transaction.RECEIVABLE,
            orig='dest', dest='dest',
            orig_account=Transaction.BACKLOG,
            orig_organization=provider,
            from_date=monday)

        _, refund_amounts = aggregate_monthly(
            provider, Transaction.REFUND,
            orig='dest', dest='dest',
            from_date=monday)

        account_table += [
            {"key": "Payments", "values": payment_amounts},
            {"key": "Refunds", "values": refund_amounts}]
        import pdb; pdb.set_trace()
