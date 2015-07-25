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

import datetime, locale, re, sys
from optparse import make_option

from django.core.management.base import BaseCommand
from django.utils.timezone import utc

# We need this import to avoid getting an exception importing 'saas.models'
from saas.utils import datetime_or_now #pylint: disable=unused-import
from saas.ledger import export
from saas.models import Organization, Transaction, get_current_provider

class Command(BaseCommand):
    help = 'Manage ledger.'
    option_list = BaseCommand.option_list + (
        make_option('--database', action='store',
            dest='database', default='default',
            help='connect to database specified.'),
        make_option('--account-first', action='store_true',
            dest='account_first', default=False,
            help='Interpret the item before the first ":" '\
'separator as the account name'),
       make_option('--create-organizations', action='store_true',
            dest='create_organizations', default=False,
            help='Create organization if it does not exist.'),
        )

    args = 'subcommand [--account-first]'
    requires_model_validation = False

    def handle(self, *args, **options):
        #pylint: disable=too-many-locals
        subcommand = args[0]
        using = options['database']
        if subcommand == 'export':
            export(sys.stdout, Transaction.objects.using(using).all())

        elif subcommand == 'import':
            account_first = options.get('account_first', False)
            create_organizations = options.get('create_organizations', False)
            filedesc = sys.stdin
            line = filedesc.readline()
            while line != '':
                look = re.match(
                    r'(?P<created_at>\d\d\d\d/\d\d/\d\d( \d\d:\d\d:\d\d)?)'\
r'\s+(#(?P<reference>\S+) -)?(?P<descr>.*)', line)
                if look:
                    # Start of a transaction
                    try:
                        created_at = datetime.datetime.strptime(
                            look.group('created_at'),
                            '%Y/%m/%d %H:%M:%S').replace(tzinfo=utc)
                    except ValueError:
                        created_at = datetime.datetime.strptime(
                            look.group('created_at'),
                            '%Y/%m/%d').replace(tzinfo=utc)
                    if look.group('reference'):
                        reference = look.group('reference').strip()
                    else:
                        reference = None
                    descr = look.group('descr').strip()
                    line = filedesc.readline()
                    dest_organization, dest_account, dest_amount \
                        = parse_line(line, account_first, create_organizations)
                    line = filedesc.readline()
                    orig_organization, orig_account, _ \
                        = parse_line(line, account_first, create_organizations)
                    if dest_organization and orig_organization:
                        # Assuming no errors, at this point we have
                        # a full transaction.
                        Transaction.objects.using(using).create(
                            created_at=created_at,
                            descr=descr,
                            dest_unit='usd',
                            dest_amount=dest_amount,
                            dest_organization=dest_organization,
                            dest_account=dest_account,
                            orig_amount=dest_amount,
                            orig_unit='usd',
                            orig_organization=orig_organization,
                            orig_account=orig_account,
                            event_id=reference)
                line = filedesc.readline()


def parse_line(line, account_first=False, create_organizations=False):
    """
    Parse an (organization, account, amount) triplet.
    """
    if account_first:
        look = re.match(r'\s+(?P<account>(\w+:)+)(?P<organization>\w+)'\
r'(\s+(?P<amount>.+))?', line)
    else:
        look = re.match(r'\s+(?P<organization>\w+)(?P<account>(:(\w+))+)'\
r'(\s+(?P<amount>.+))?', line)
    if look:
        organization_slug = look.group('organization')
        account = look.group('account')
        if account.startswith(':'):
            account = account[1:]
        if account.endswith(':'):
            account = account[:-1]
        amount = look.group('amount')
        if amount and amount.startswith('$'):
            locale.setlocale(locale.LC_ALL, 'en_US')
            amount = long(locale.atof(amount[1:]) * 100)
        try:
            if create_organizations:
                organization, _ = Organization.objects.get_or_create(
                    slug=organization_slug)
            else:
                organization = Organization.objects.get(slug=organization_slug)
            if account_first:
                organization = get_current_provider()
            return (organization, account, amount)
        except Organization.DoesNotExist:
            print "Cannot find Organization '%s'" % organization_slug
    return (None, None, None)
