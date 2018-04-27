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

import datetime

from django.db import connection

from .humanize import as_money


def read_balances(account, until=datetime.datetime.now()):
    """Balances associated to customer accounts.

    We are executing the following SQL to find the balance
    of each customer.

    The query returns a list of tuples (organization_id, amount in cents)
    we use to create the invoices.
    example:
        (2, 1200)
        (3, 1100)

    """
    cursor = connection.cursor()
    cursor.execute(
"""select t1.dest_organization_id,
     sum(t1.dest_amount - coalesce(t2.dest_amount, 0))
from saas_transaction t1 left outer join saas_transaction t2
on t1.dest_organization_id = t2.orig_organization_id
   and t1.dest_account = t2.orig_account
where t1.dest_account = '%s' and t1.created_at < '%s' and t2.created_at < '%s'
group by t1.dest_organization_id
""" % (account, until, until))
    return cursor.fetchall()


def export(output, transactions):
    """
    Export a set of Transaction in ledger format.
    """
    for transaction in transactions:
        dest = ("\t\t%(dest_organization)s:%(dest_account)s"
                % {'dest_organization': transaction.dest_organization,
                   'dest_account': transaction.dest_account})
        dest_amount = as_money(transaction.dest_amount,
            transaction.dest_unit).rjust(60 - len(dest))
        orig = ("\t\t%(orig_organization)s:%(orig_account)s"
                % {'orig_organization': transaction.orig_organization,
                   'orig_account': transaction.orig_account})
        if transaction.dest_unit != transaction.orig_unit:
            disp_orig_amount = "-%s" % as_money(transaction.orig_amount,
                transaction.orig_unit)
            orig_amount = disp_orig_amount.rjust(60 - len(orig))
        else:
            orig_amount = ''
        output.write("""
%(created_at)s #%(reference)s - %(description)s
%(dest)s%(dest_amount)s
%(orig)s%(orig_amount)s
""" % {'created_at': datetime.datetime.strftime(
            transaction.created_at, '%Y/%m/%d %H:%M:%S'),
        'reference': '%s' % transaction.event_id,
        'description': transaction.descr,
        'dest': dest, 'dest_amount': dest_amount,
        'orig': orig, 'orig_amount': orig_amount})
