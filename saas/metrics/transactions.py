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

from django.db import connection
from django.db.models import F, Sum

from .. import settings
from ..compat import six
from ..models import Transaction

LOGGER = logging.getLogger(__name__)


def lifetime_value(provider=None):
    #pylint:disable=too-many-locals,too-many-statements

    # Contract value (i.e. "Total Sales")
    kwargs = {'orig_organization': provider} if provider else {}
    contract_values = Transaction.objects.filter(
        dest_account=Transaction.PAYABLE, **kwargs).values(
        slug=F('dest_organization__slug')).annotate(
        amount=Sum('orig_amount'), unit=F('orig_unit')).order_by(
        'dest_organization__slug')
    by_profiles = {val['slug']: {'contract_value': {val['unit']: val['amount']}}
        for val in contract_values}

    # Payments
    # Transfers of funds to provider. The only sources are
    # processor:Funds (online) and subscriber:Liability (offline).
    #
    # Payments of funds from subscriber shows as subscriber:Liability
    # to provider:Funds transactions.
    if provider:
        provider_clause = "AND dest_organization_id = %d" % provider.pk
    else:
        provider_clause = ("AND NOT dest_organization_id IN (%d)" %
            settings.PROCESSOR_ID)
    payments_query = """WITH transfers AS (
  SELECT * FROM saas_transaction
  WHERE dest_account='%(funds)s'
    %(provider_clause)s),
payments AS (
  SELECT * FROM saas_transaction
  WHERE dest_account='%(funds)s' AND orig_account='%(liability)s'
    AND dest_organization_id IN %(processor_ids)s)
SELECT saas_organization.slug, transfers.dest_unit, SUM(transfers.dest_amount)
FROM transfers
INNER JOIN payments
  ON transfers.event_id = payments.event_id
INNER JOIN saas_organization
  ON saas_organization.id = payments.orig_organization_id
GROUP BY saas_organization.slug, transfers.dest_unit""" % {
            'provider_clause': provider_clause,
            'processor_ids': '(%d)' % settings.PROCESSOR_ID,
            'funds': Transaction.FUNDS,
            'liability': Transaction.LIABILITY
        }

    with connection.cursor() as cursor:
        cursor.execute(payments_query, params=None)
        for row in cursor.fetchall():
            organization_slug = row[0]
            unit = row[1]
            amount = row[2]
            account = Transaction.LIABILITY
            if organization_slug not in by_profiles:
                by_profiles[organization_slug] = {unit: {account: amount}}
            else:
                if unit not in by_profiles[organization_slug]:
                    by_profiles[organization_slug].update({
                        unit: {account: amount}})
                else:
                    by_profiles[organization_slug][unit].update({
                        account: amount})

    kwargs = {'dest_organization': provider} if provider else {}
    refunds = Transaction.objects.filter(
        dest_account=Transaction.REFUND,
        orig_account=Transaction.REFUNDED, **kwargs).values(
        slug=F('orig_organization__slug'), unit=F('orig_unit')).annotate(
        amount=Sum('orig_amount')).order_by(
        'orig_organization__slug')
    for val in refunds:
        organization_slug = val['slug']
        unit = val['unit']
        amount = val['amount']
        account = val['account']
        if organization_slug not in by_profiles:
            by_profiles[organization_slug] = {unit: {account: amount}}
        else:
            if unit not in by_profiles[organization_slug]:
                by_profiles[organization_slug].update({unit: {account: amount}})
            else:
                by_profiles[organization_slug][unit].update({account: amount})

    # deferred revenue
    deferred_revenues_query = """
SELECT saas_organization.slug, saas_transaction.dest_unit,
  SUM(saas_transaction.dest_amount)
FROM saas_organization
INNER JOIN saas_subscription
  ON saas_organization.id = saas_subscription.organization_id
INNER JOIN saas_plan
  ON saas_subscription.plan_id = saas_plan.id
INNER JOIN saas_transaction
  ON cast(substr(saas_transaction.event_id, 5) AS integer)
     = saas_subscription.id
WHERE saas_transaction.dest_account = '%(backlog)s'
%(provider_clause)s
GROUP BY saas_organization.slug, saas_transaction.dest_unit
""" % {'backlog': Transaction.BACKLOG,
       'provider_clause': ("AND saas_plan.organization_id = %d" % provider.pk
            if provider else "")}

    with connection.cursor() as cursor:
        cursor.execute(deferred_revenues_query, params=None)
        for row in cursor.fetchall():
            slug = row[0]
            unit = row[1]
            amount = row[2]
            account = Transaction.BACKLOG
            if organization_slug not in by_profiles:
                by_profiles[organization_slug] = {unit: {account: amount}}
            else:
                if unit not in by_profiles[organization_slug]:
                    by_profiles[organization_slug].update({
                        unit: {account: amount}})
                else:
                    by_profiles[organization_slug][unit].update({
                        account: amount})

    results = {}
    for slug, by_units in six.iteritems(by_profiles):
        for unit, val in six.iteritems(by_units):
            liability = val.get(Transaction.LIABILITY, 0)
            backlog = val.get(Transaction.BACKLOG, 0)
            deferred_revenue = liability - backlog if liability > backlog else 0
            val.update({
                'contract_value': val.get('contract_value', 0),
                'payments': (liability - val.get(Transaction.REFUNDED, 0)),
                'deferred_revenue': deferred_revenue
            })
            if slug not in results:
                results[slug] = {unit: val}
            else:
                if unit not in results[slug]:
                    results[slug].update({unit: val})
                else:
                    results[slug][unit].update(val)

    return results
