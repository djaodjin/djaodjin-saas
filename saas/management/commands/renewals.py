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

"""
The renewals command is intended to be run as part of an automated scripts
run at least once a day. It will

- recognize revenue for past periods (see :doc:`ledger <ledger>`).
- extends active subscriptions
- create charges for new periods

Every functions part of the renewals script are explicitly written to be
idempotent. Calling the scripts multiple times for the same timestamp
(i.e. with the ``--at-time`` command line argument) will generate the
appropriate ``Transaction`` and ``Charge`` only once.

**Example cron setup**:

.. code-block:: bash

    $ cat /etc/cron.daily/renewals
    #!/bin/sh

    cd /var/*mysite* && python manage.py renewals
"""

import logging, time

from django.core.management.base import BaseCommand

from ...charge import (recognize_income, extend_subscriptions,
    create_charges_for_balance, complete_charges)
from ...utils import datetime_or_now


LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Recognized backlog, extends subscription and charge due balance
on credit cards"""

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
            dest='dry_run', default=False,
            help='Do not commit transactions nor submit charges to processor')
        parser.add_argument('--no-charges', action='store_true',
            dest='no_charges', default=False,
            help='Do not submit charges to processor')
        parser.add_argument('--at-time', action='store',
            dest='at_time', default=None,
            help='Specifies the time at which the command runs')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        no_charges = options['no_charges']
        end_period = datetime_or_now(options['at_time'])
        if dry_run:
            LOGGER.warning("dry_run: no changes will be committed.")
        if no_charges:
            LOGGER.warning("no_charges: no charges will be submitted.")
        recognize_income(end_period, dry_run=dry_run)
        extend_subscriptions(end_period, dry_run=dry_run)
        create_charges_for_balance(end_period, dry_run=dry_run or no_charges)
        if not (dry_run or no_charges):
            # Let's complete the in flight charges after we have given
            # them time to settle.
            time.sleep(30)
            complete_charges()
