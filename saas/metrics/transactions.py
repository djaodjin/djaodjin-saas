# Copyright (c) 2020, DjaoDjin inc.
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

import logging

from dateutil.relativedelta import relativedelta
from django.db import connection
from django.db.models import F, Q, Sum

from .. import settings
from ..compat import six
from ..models import Transaction
from ..utils import datetime_or_now

LOGGER = logging.getLogger(__name__)


def lifetime_value():
    # Contract value
    contract_values = Transaction.objects.filter(
        dest_account=Transaction.PAYABLE).values(
        slug=F('dest_organization__slug')).annotate(
        amount=Sum('orig_amount')).order_by(
        'dest_organization__slug')

    print("XXX contract_values.query=%s" % str(contract_values.query))

    # Cash payments
    cash_payments = Transaction.objects.filter(
        (Q(dest_organization_id=settings.PROCESSOR_ID) &
         Q(dest_account=Transaction.FUNDS))
        | Q(dest_account=Transaction.REFUND)).values(
        slug=F('orig_organization__slug'), account=F('orig_account')).annotate(
        amount=Sum('orig_amount')).order_by(
        'orig_organization__slug')

    print("XXX cash_payments.query=%s" % str(cash_payments.query))

    by_profiles = {val['slug']: {'contract_value': val['amount']} for val in contract_values}
    for val in cash_payments:
        if val['slug'] not in by_profiles:
            by_profiles[val['slug']] = {val['account']: val['amount']}
        else:
            by_profiles[val['slug']].update({val['account']: val['amount']})

    # deferred revenue
    deferred_revenues_query = """
SELECT saas_organization.slug, SUM(saas_transaction.dest_amount)
FROM saas_organization
INNER JOIN saas_subscription
  ON saas_organization.id = saas_subscription.organization_id
INNER JOIN saas_transaction
  ON saas_transaction.event_id = concat('sub_', saas_subscription.id, '/')
WHERE saas_transaction.dest_account = '%(backlog)s'
GROUP BY saas_organization.slug
""" % {'backlog': Transaction.BACKLOG}
    print("XXX deferred_revenues_query=%s" % str(deferred_revenues_query))

    with connection.cursor() as cursor:
        cursor.execute(deferred_revenues_query, params=None)
        for row in cursor.fetchall():
            slug = row[0]
            amount = row[1]
            if slug not in by_profiles:
                by_profiles[slug] = {Transaction.BACKLOG: amount}
            else:
                by_profiles[slug].update({Transaction.BACKLOG: amount})

    results = []
    for slug, val in six.iteritems(by_profiles):
        liability = val.get('Liability', 0)
        backlog = val.get('Backlog', 0)
        deferred_revenue = liability - backlog if liability > backlog else 0
        val.update({
            'slug': slug,
            'contract_value': val.get('contract_value', 0),
            'cash_payments': val.get('Liability', 0) - val.get('Refunded', 0),
            'deferred_revenue': deferred_revenue
        })
        results += [val]

    return results
