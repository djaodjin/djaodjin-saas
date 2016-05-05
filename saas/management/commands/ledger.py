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

import datetime, re, sys

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import utc

from ...ledger import export
from ...models import Organization, Transaction

class Command(BaseCommand):
    help = 'Import/export transactions in ledger format.'

    requires_model_validation = False

    def add_arguments(self, parser):
        parser.add_argument('--database', action='store',
            dest='database', default='default',
            help='connect to database specified.')
        parser.add_argument('--broker', action='store',
            dest='broker', default='default',
            help='broker for the site')
        parser.add_argument('--create-organizations', action='store_true',
            dest='create_organizations', default=False,
            help='Create organization if it does not exist.')
        parser.add_argument('subcommand', metavar='subcommand', nargs='+',
            help="subcommand: export|import")

    def handle(self, *args, **options):
        #pylint: disable=too-many-locals
        subcommand = options['subcommand'][0]
        using = options['database']
        if subcommand == 'export':
            export(self.stdout, Transaction.objects.using(using).all().order_by(
                'created_at'))

        elif subcommand == 'import':
            broker = options.get('broker', None)
            create_organizations = options.get('create_organizations', False)
            for arg in args[1:]:
                if arg == '-':
                    import_transactions(sys.stdin,
                        create_organizations, broker, using=using)
                else:
                    with open(arg) as filedesc:
                        import_transactions(filedesc,
                            create_organizations, broker, using=using)


def import_transactions(filedesc, create_organizations=False, broker=None,
                        using='default'):
    #pylint:disable=too-many-locals
    with transaction.atomic():
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
                dest_organization, dest_account, dest_amount, dest_unit \
                    = parse_line(line, create_organizations,
                        broker=broker, using=using)
                line = filedesc.readline()
                orig_organization, orig_account, orig_amount, orig_unit \
                    = parse_line(line, create_organizations,
                        broker=broker, using=using)
                if dest_unit != 'usd' and orig_unit == 'usd':
                    dest_amount = - orig_amount
                    dest_unit = orig_unit
                if not orig_amount:
                    orig_amount = dest_amount
                if not orig_unit:
                    orig_unit = dest_unit
                if dest_organization and orig_organization:
                    # Assuming no errors, at this point we have
                    # a full transaction.
                    Transaction.objects.using(using).create(
                        created_at=created_at,
                        descr=descr,
                        dest_unit=dest_unit,
                        dest_amount=dest_amount,
                        dest_organization=dest_organization,
                        dest_account=dest_account,
                        orig_amount=dest_amount,
                        orig_unit=orig_unit,
                        orig_organization=orig_organization,
                        orig_account=orig_account,
                        event_id=reference)
            line = filedesc.readline()


MONEY_PAT = r'(?P<prefix>\$?)(?P<value>-?((\d|,)+(.\d+)?))\s*(?P<suffix>(\w+)?)'


def parse_line(line, create_organizations=False, broker=None, using='default'):
    """
    Parse an (organization, account, amount) triplet.
    """
    unit = None
    amount = None
    look = re.match(r'\s+(?P<tags>\w(\w|:)+)(\s+(?P<amount>.+))?', line)
    if look:
        organization_slug = broker
        account_parts = []
        for tag in look.group('tags').split(':'):
            if tag[0].islower():
                organization_slug = tag
            else:
                account_parts += [tag]
        account = ':'.join(account_parts)
        if look.group('amount'):
            look = re.match(MONEY_PAT, look.group('amount'))
            if look:
                unit = look.group('prefix')
                if unit is None:
                    unit = look.group('suffix')
                elif unit == '$':
                    unit = 'usd'
                value = look.group('value').replace(',', '')
                if '.' in value:
                    amount = long(float(value) * 100)
                else:
                    amount = long(value)
        try:
            if create_organizations:
                organization, _ = Organization.objects.using(
                    using).get_or_create(slug=organization_slug)
            else:
                organization = Organization.objects.using(using).get(
                    slug=organization_slug)
            return (organization, account, amount, unit)
        except Organization.DoesNotExist:
            sys.stderr.write("error: Cannot find Organization '%s'\n"
                % organization_slug)
    return (None, None, None)
