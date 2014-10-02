# Copyright (c) 2014, DjaoDjin inc.
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

import datetime, re, sys

from django.core.management.base import BaseCommand
from django.utils.timezone import utc
# We need this import to avoid getting an exception importing 'saas.models'
from saas.utils import datetime_or_now #pylint: disable=unused-import
from saas.models import Organization, Transaction

class Command(BaseCommand):
    help = 'Manage ledger.'
    args = 'subcommand'
    requires_model_validation = False

    def handle(self, *args, **options):
        #pylint: disable=too-many-locals
        subcommand = args[0]
        if subcommand == 'export':
            for transaction in Transaction.objects.all():
                dest = ("\t\t%(dest_organization)s:%(dest_account)s"
                    % {'dest_organization': transaction.dest_organization,
                       'dest_account': transaction.dest_account})
                amount_str = ('%s' % transaction.dest_amount).rjust(
                    60 - len(dest))
                sys.stdout.write("""
%(date)s #%(reference)s - %(description)s
%(dest)s%(amount)s
\t\t%(orig_organization)s:%(orig_account)s
""" % {'date': datetime.datetime.strftime(
            transaction.created_at, '%Y/%m/%d %H:%M:%S'),
        'reference': transaction.event_id,
        'description': transaction.descr,
        'dest': dest,
        'amount': amount_str,
        'orig_organization': transaction.orig_organization,
        'orig_account': transaction.orig_account})

        elif subcommand == 'import':
            descr = None
            amount = None
            reference = None
            created_at = None
            orig_account = None
            dest_account = None
            orig_organization = None
            dest_organization = None
            for line in sys.stdin.readlines():
                look = re.match(
                  r'(\d\d\d\d/\d\d/\d\d \d\d:\d\d:\d\d)\s+#(\S+) - (.*)', line)
                if look:
                    # Start of a transaction
                    created_at = datetime.datetime.strptime(look.group(1),
                        '%Y/%m/%d %H:%M:%S').replace(tzinfo=utc)
                    reference = look.group(2).strip()
                    descr = look.group(3).strip()
                else:
                    look = re.match(r'\s+(\w+):(\w+)\s+(.+)', line)
                    if look:
                        dest_organization = Organization.objects.get(
                            slug=look.group(1))
                        dest_account = look.group(2)
                        amount = look.group(3)
                    else:
                        look = re.match(r'\s+(\w+):(\w+)', line)
                        if look:
                            orig_organization = Organization.objects.get(
                                slug=look.group(1))
                            orig_account = look.group(2)
                            # Assuming no errors, at this point we have
                            # a full transaction.
                            Transaction.objects.create(
                                created_at=created_at,
                                descr=descr,
                                orig_amount=amount,
                                dest_amount=amount,
                                dest_organization=dest_organization,
                                dest_account=dest_account,
                                orig_organization=orig_organization,
                                orig_account=orig_account,
                                event_id=reference)
