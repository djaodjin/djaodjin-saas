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

from django.db import connection, router
from django.db.models import F, Sum

from .. import settings
from ..compat import six
from ..models import Transaction, is_sqlite3

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
    by_profiles = {val['slug']: {val['unit']: {'contract_value': val['amount']}}
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
    # We need a `DISTINCT` statement for charges that pay
    # multiple subscriptions to the same provider.
    payments_query = """WITH transfers AS (
  SELECT * FROM saas_transaction
  WHERE orig_account='%(funds)s' AND
    (dest_account='%(funds)s' OR dest_account='%(offline)s')
    %(provider_clause)s),
payments AS (
  SELECT * FROM saas_transaction
  WHERE orig_account='%(liability)s' AND
    dest_account='%(funds)s' AND dest_organization_id IN %(processor_ids)s),
matched_transfers_payments AS (
  SELECT DISTINCT payments.event_id, payments.orig_organization_id,
    payments.dest_unit, payments.dest_amount
  FROM transfers
  INNER JOIN payments
    ON transfers.event_id = payments.event_id)
SELECT saas_organization.slug, matched_transfers_payments.dest_unit,
  SUM(matched_transfers_payments.dest_amount)
FROM matched_transfers_payments
INNER JOIN saas_organization
  ON saas_organization.id = matched_transfers_payments.orig_organization_id
GROUP BY saas_organization.slug, matched_transfers_payments.dest_unit""" % {
            'provider_clause': provider_clause,
            'processor_ids': '(%d)' % settings.PROCESSOR_ID,
            'funds': Transaction.FUNDS,
            'offline': Transaction.OFFLINE,
            'liability': Transaction.LIABILITY
        }
    # XXX transfers: without processor fee, payments: with processor fee.
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
        account = Transaction.REFUNDED
        if organization_slug not in by_profiles:
            by_profiles[organization_slug] = {unit: {account: amount}}
        else:
            if unit not in by_profiles[organization_slug]:
                by_profiles[organization_slug].update({unit: {account: amount}})
            else:
                by_profiles[organization_slug][unit].update({account: amount})

    # deferred revenue
    if is_sqlite3(router.db_for_read(Transaction)):
        extract_number = 'substr(saas_transaction.event_id, 5)'
    else:
        # We would use `substr(saas_transaction.event_id, 5)` which is syntax-
        # compatible if it were not for Postgresql to through an execption on
        # the trailing '/' character.
        extract_number = (
            r"substring(saas_transaction.event_id from 'sub_(\d+)/')")
    deferred_revenues_query = """
SELECT saas_organization.slug, saas_transaction.dest_unit,
  SUM(saas_transaction.dest_amount)
FROM saas_organization
INNER JOIN saas_subscription
  ON saas_organization.id = saas_subscription.organization_id
INNER JOIN saas_plan
  ON saas_subscription.plan_id = saas_plan.id
INNER JOIN saas_transaction
  ON cast(%(extract_number)s AS integer)
     = saas_subscription.id
WHERE saas_transaction.dest_account = '%(backlog)s'
%(provider_clause)s
GROUP BY saas_organization.slug, saas_transaction.dest_unit
""" % {'backlog': Transaction.BACKLOG,
       'extract_number': extract_number,
       'provider_clause': ("AND saas_plan.organization_id = %d" % provider.pk
            if provider else "")}
    with connection.cursor() as cursor:
        cursor.execute(deferred_revenues_query, params=None)
        for row in cursor.fetchall():
            organization_slug = row[0]
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
            payments = (val.get(Transaction.LIABILITY, 0)
                - val.get(Transaction.REFUNDED, 0))
            backlog = val.get(Transaction.BACKLOG, 0)
            deferred_revenue = payments - backlog if payments > backlog else 0
            val.update({
                'contract_value': val.get('contract_value', 0),
                'payments': payments,
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
