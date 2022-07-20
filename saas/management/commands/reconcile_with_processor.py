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

"""
The reconcile_with_processor command is will check all payouts on the processor
have been accounted for in the local database.
"""

import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from ...utils import datetime_or_now, get_organization_model
from ...backends import ProcessorError


LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Reconcile processor payouts with transactions in the local
 database"""

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
            dest='dry_run', default=False,
            help='Do not commit transactions')
        parser.add_argument('--after', action='store',
            dest='after', default=None,
           help='Only accounts for records created *after* a specific datetime')
        parser.add_argument('--at-time', action='store',
            dest='at_time', default=None,
            help='Specifies the time at which the command runs')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        created_at = options['after']
        if created_at:
            created_at = datetime_or_now(created_at)
        # XXX currently unused
        # end_period = datetime_or_now(options['at_time'])
        if dry_run:
            LOGGER.warning("dry_run: no changes will be committed.")
        self.run_reconcile(created_at=created_at, dry_run=dry_run)

    def run_reconcile(self, created_at=None, dry_run=False):
        for provider in get_organization_model().objects.filter(is_provider=True):
            self.stdout.write("reconcile payouts for %s ..." % str(provider))
            backend = provider.processor_backend
            if not created_at:
                created_at = provider.created_at
            try:
                with transaction.atomic():
                    backend.reconcile_transfers(provider, created_at,
                        dry_run=dry_run)
            except ProcessorError as err:
                self.stderr.write("error: %s" % str(err))
