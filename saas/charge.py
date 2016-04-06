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
Dealing with charges
"""

import logging

from dateutil.relativedelta import relativedelta
from django.db import transaction

from .humanize import DESCRIBE_RECOGNIZE_INCOME
from .models import (Charge, Organization, Transaction, Subscription,
    sum_dest_amount)
from .utils import datetime_or_now

LOGGER = logging.getLogger(__name__)


def recognize_income(until=None, dry_run=False):
    """
    Create all ``Transaction`` necessary to recognize revenue
    on each ``Subscription`` until date specified.
    """
    #pylint:disable=too-many-locals
    until = datetime_or_now(until)
    LOGGER.info("recognize income until %s ...", until)
    for subscription in Subscription.objects.filter(created_at__lte=until):
        # We need to pass through subscriptions otherwise we won't recognize
        # income on the ones that were just cancelled.
        with transaction.atomic():
            # [``recognize_start``, ``recognize_end``[ is one period over which
            # revenue is recognized. It will slide over the subscription
            # lifetime from ``created_at`` to ``until``.
            to_recognize_amount = 0
            recognize_period = relativedelta(months=1)
            order_subscribe_beg = subscription.created_at
            recognize_start = subscription.created_at
            recognize_end = recognize_start + recognize_period
            LOGGER.debug('process %s (%d transactions)',
                subscription, Transaction.objects.get_subscription_receivable(
                    subscription, until=until).count())
            for order in Transaction.objects.get_subscription_receivable(
                    subscription, until=until):
                # [``order_subscribe_beg``, ``order_subscribe_end``[ is
                # the subset of the subscription lifetime the order paid for.
                # It covers ``total_periods`` plan periods.
                total_periods = order.get_event().plan.period_number(
                    order.descr)
                order_subscribe_end = subscription.plan.end_of_period(
                    order_subscribe_beg, nb_periods=total_periods)
                min_end = min(order_subscribe_end, until)
                LOGGER.debug('\tprocess order %d of %dc covering [%s, %s['\
                    ' (%s periods) until %s', order.id, order.dest_amount,
                    order_subscribe_beg, order_subscribe_end,
                    total_periods, min_end)
                while recognize_end <= min_end:
                    # we use ``<=`` here because we compare that bounds
                    # are equal instead of searching for points within
                    # the interval.
                    nb_periods = subscription.nb_periods(
                        recognize_start, recognize_end)
                    to_recognize_amount = (
                        nb_periods * order.dest_amount) / total_periods
                    recognized_amount, _ = \
                        Transaction.objects.get_subscription_income_balance(
                            subscription,
                            starts_at=recognize_start,
                            ends_at=recognize_end)
                    # We are not computing a balance sheet here but looking for
                    # a positive amount to compare with the revenue that should
                    # have been recognized.
                    recognized_amount = abs(recognized_amount)
                    LOGGER.debug("%dc to recognize vs. %dc recognized in "\
                        "[%s, %s[", to_recognize_amount, recognized_amount,
                        recognize_start, recognize_end)
                    if to_recognize_amount > recognized_amount:
                        # We have some amount of revenue to recognize here.
                        # ``at_time`` is set just before ``recognize_end``
                        # so we do not include the newly created transaction
                        # in the subsequent period.
                        amount = to_recognize_amount - recognized_amount
                        at_time = recognize_end - relativedelta(seconds=1)
                        LOGGER.info(
                            'RECOGNIZE %dc for %s:%s in [%s, %s[',
                            amount, subscription.organization,
                            subscription.plan, recognize_start, recognize_end)
                        if not dry_run:
                            Transaction.objects.create_income_recognized(
                                subscription, amount=amount, at_time=at_time,
                                descr=DESCRIBE_RECOGNIZE_INCOME % {
                                    'subscription': subscription,
                                    'nb_periods': nb_periods,
                                    'period_start': recognize_start,
                                    'period_end': recognize_end})
                    recognize_start = recognize_end
                    recognize_end += recognize_period
                order_subscribe_beg = order_subscribe_end
                if recognize_end >= until:
                    break


def extend_subscriptions(at_time=None, dry_run=False):
    """
    Extend active subscriptions
    """
    at_time = datetime_or_now(at_time)
    LOGGER.info("extend subscriptions at %s ...", at_time)
    for subscription in Subscription.objects.filter(
            auto_renew=True, created_at__lte=at_time, ends_at__gt=at_time):
        _, upper = subscription.period_for(at_time)
        if upper == subscription.ends_at:
            # We are in the last period
            LOGGER.info('EXTENDS subscription of %s to %s at %s for 1 period',
                subscription.organization, subscription.plan,
                subscription.ends_at)
            if not dry_run:
                with transaction.atomic():
                    _ = Transaction.objects.execute_order([
                        Transaction.objects.new_subscription_order(
                            subscription, 1, created_at=at_time)])


def create_charges_for_balance(until=None, dry_run=False):
    """
    Create charges for all accounts payable.
    """
    until = datetime_or_now(until)
    LOGGER.info("create charges for balance at %s ...", until)
    for organization in Organization.objects.all():
        charges = Charge.objects.filter(
            customer=organization, state=Charge.CREATED)
        # We will create charges only when we have no charges
        # already in flight for this customer.
        if not charges.exists():
            invoiceables = Transaction.objects.get_invoiceables(
                organization, until=until)
            balance = sum_dest_amount(invoiceables)
            invoiceable_amount = balance['amount']
            if invoiceable_amount > 50:
                # Stripe will not processed charges less than 50 cents.
                LOGGER.info('CHARGE %dc to %s', invoiceable_amount,
                    organization)
                try:
                    if not dry_run:
                        Charge.objects.charge_card(organization, invoiceables)
                except:
                    raise
            elif invoiceable_amount > 0:
                LOGGER.info('SKIP   %dc to %s (less than 50c)',
                    invoiceable_amount, organization)
        else:
            LOGGER.info('SKIP   %s (one charge already in flight)',
                organization)


def complete_charges():
    """
    Update the state of all charges in progress.
    """
    for charge in Charge.objects.filter(state=Charge.CREATED):
        charge.retrieve()
