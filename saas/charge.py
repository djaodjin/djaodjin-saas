# Copyright (c) 2015, DjaoDjin inc.
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

from saas.humanize import DESCRIBE_RECOGNIZE_INCOME
from saas.models import (Charge, Organization, Transaction, Subscription,
    sum_dest_amount)
from saas.utils import datetime_or_now

LOGGER = logging.getLogger(__name__)


def recognize_income(until=None):
    """
    Create all ``Transaction`` necessary to recognize revenue
    on each ``Subscription`` until date specified.
    """
    until = datetime_or_now(until)
    for subscription in Subscription.objects.filter(
            created_at__lte=until, ends_at__gt=until):
        with transaction.atomic():
            # [``recognize_start``, ``recognize_end``[ is one period over which
            # revenue is recognized. It will slide over the subscription
            # lifetime from ``created_at`` to ``until``.
            to_recognize_amount = 0
            recognize_period = relativedelta(months=1)
            order_subscribe_beg = subscription.created_at
            recognize_start = subscription.created_at
            recognize_end = recognize_start + recognize_period
            for order in Transaction.objects.get_subscription_receivable(
                    subscription):
                # [``order_subscribe_beg``, ``order_subscribe_end``[ is
                # the subset of the subscription lifetime the order paid for.
                # It covers ``total_periods`` plan periods.
                total_periods = order.get_event().plan.period_number(
                    order.descr)
                order_subscribe_end = subscription.plan.end_of_period(
                    order_subscribe_beg, nb_periods=total_periods)
                min_end = min(order_subscribe_end, until)
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
                    if to_recognize_amount > recognized_amount:
                        # We have some amount of revenue to recognize here.
                        # ``at_time`` is set just before ``recognize_end``
                        # so we do not include the newly created transaction
                        # in the subsequent period.
                        Transaction.objects.create_income_recognized(
                            subscription,
                            amount=to_recognize_amount - recognized_amount,
                            at_time=recognize_end - relativedelta(seconds=1),
                            descr=DESCRIBE_RECOGNIZE_INCOME % {
                            'period_start': recognize_start,
                            'period_end': recognize_end})
                    recognize_start = recognize_end
                    recognize_end += recognize_period
                order_subscribe_beg = order_subscribe_end
                if recognize_end >= until:
                    break


def extend_subscriptions(at_time=None):
    """
    Extend active subscriptions
    """
    for subscription in Subscription.objects.filter(
            auto_renew=True, created_at__lte=at_time, ends_at__gt=at_time):
        _, upper = subscription.period_for(at_time)
        if upper == subscription.ends_at:
            # We are in the last period
            with transaction.atomic():
                _ = Transaction.objects.execute_order([
                    Transaction.objects.new_subscription_order(
                        subscription, 1, created_at=at_time)])


def create_charges_for_balance(until=None):
    """
    Create charges for all accounts payable.
    """
    for organization in Organization.objects.all():
        charges = Charge.objects.filter(
            customer=organization, state=Charge.CREATED)
        # We will create charges only when we have no charges
        # already in flight for this customer.
        if not charges.exists():
            invoiceables = Transaction.objects.get_invoiceables(
                organization, until=until)
            invoiceable_amount, _ = sum_dest_amount(invoiceables)
            if invoiceable_amount > 50:
                # Stripe will not processed charges less than 50 cents.
                LOGGER.info('CHARGE %dc to %s', invoiceable_amount,
                    organization)
                try:
                    Charge.objects.charge_card(organization, invoiceables)
                except:
                    raise
            else:
                LOGGER.info('SKIP   %s (less than 50c)', organization)
        else:
            LOGGER.info('SKIP   %s (one charge already in flight)',
                organization)
