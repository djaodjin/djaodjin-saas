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

"""Command for the cron job. Create credit card charges"""

from optparse import make_option

from django.core.management.base import BaseCommand

from ...charge import (recognize_income, extend_subscriptions,
    create_charges_for_balance)
from ...utils import datetime_or_now

class Command(BaseCommand):
    """Charges for due balance"""

    help = "Recognized backlog and charge due balance on credit cards"
    option_list = BaseCommand.option_list + (
        make_option('--dry-run', action='store_true',
            dest='dry_run', default=False,
            help='Do not commit execution'),
        make_option('--at-time', action='store',
            dest='at_time', default=None,
            help='Specifies the time at which the command runs'))

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        end_period = datetime_or_now(options['at_time'])
        recognize_income(end_period, dry_run=dry_run)
        extend_subscriptions(end_period, dry_run=dry_run)
        create_charges_for_balance(end_period, dry_run=dry_run)
