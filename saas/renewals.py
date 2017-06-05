# Copyright (c) 2017, DjaoDjin inc.
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
The functions defined in the module are meant to be run regularly
in batch mode.
"""

import logging

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import six

from . import humanize, signals
from .models import (Charge, Organization, Plan, Subscription, Transaction,
    sum_dest_amount)
from .utils import datetime_or_now

LOGGER = logging.getLogger(__name__)


class DryRun(RuntimeError):

    pass


def _recognize_subscription_income(subscription, until=None):
    #pylint:disable=too-many-locals
    until = datetime_or_now(until)
    # [``recognize_start``, ``recognize_end``[ is one period over which
    # revenue is recognized. It will slide over the subscription
    # lifetime from ``created_at`` to ``until``.
    order_subscribe_beg = subscription.created_at
    recognize_period_idx = 0
    recognize_start = subscription.created_at
    recognize_end = (subscription.created_at
        + relativedelta(months=recognize_period_idx + 1))
    LOGGER.debug('process %s', subscription)
    for order in Transaction.objects.get_subscription_receivable(
            subscription, until=until):
        # [``order_subscribe_beg``, ``order_subscribe_end``[ is
        # the subset of the subscription lifetime the order paid for.
        # It covers ``order_periods`` plan periods.
        order_amount = order.dest_amount
        order_periods = order.get_event().plan.period_number(order.descr)
        order_subscribe_end = subscription.plan.end_of_period(
            order_subscribe_beg, nb_periods=order_periods)
        min_end = min(order_subscribe_end, until)
        LOGGER.debug('\tprocess order %d %s of %dc covering [%s, %s['\
            ' (%s periods) until %s', order.id,
            subscription, order.dest_amount,
            order_subscribe_beg, order_subscribe_end,
            order_periods, min_end)
        while recognize_end <= min_end:
            # we use ``<=`` here because we compare that bounds
            # are equal instead of searching for points within
            # the interval.
            nb_periods = subscription.nb_periods(
                recognize_start, recognize_end)
            # XXX integer division
            to_recognize_amount = int(
                (nb_periods * order_amount) // order_periods)
            assert isinstance(to_recognize_amount, six.integer_types)
            balance = Transaction.objects.get_subscription_income_balance(
                subscription, starts_at=recognize_start, ends_at=recognize_end)
            recognized_amount = balance['amount']
            # We are not computing a balance sheet here but looking for
            # a positive amount to compare with the revenue that should
            # have been recognized.
            recognized_amount = abs(recognized_amount)
            LOGGER.debug("%dc (%s * %dc / %s) to recognize"\
                " vs. %dc recognized in [%s, %s[", to_recognize_amount,
                str(nb_periods), order_amount, str(order_periods),
                recognized_amount, recognize_start, recognize_end)
            if to_recognize_amount > recognized_amount:
                # We have some amount of revenue to recognize here.
                amount = to_recognize_amount - recognized_amount
                descr_period_start = recognize_start
                descr_period_end = recognize_end
                if nb_periods == 1.0:
                    descr = humanize.DESCRIBE_RECOGNIZE_INCOME
                    if subscription.plan.interval > Plan.DAILY:
                        descr_period_start = recognize_start.date()
                        # shows the natural bound for "end of day".
                        descr_period_end = (
                            recognize_end - relativedelta(days=1)).date()
                else:
                    descr = humanize.DESCRIBE_RECOGNIZE_INCOME_DETAILED
                Transaction.objects.create_income_recognized(
                    subscription, amount=amount,
                    starts_at=recognize_start, ends_at=recognize_end,
                    descr=descr % {
                        'subscription': subscription,
                        'nb_periods': nb_periods,
                        'period_start': descr_period_start,
                        'period_end': descr_period_end})
            recognize_period_idx += 1
            recognize_start = (subscription.created_at
                + relativedelta(months=recognize_period_idx))
            recognize_end = (subscription.created_at
                + relativedelta(months=recognize_period_idx + 1))
        order_subscribe_beg = order_subscribe_end
        if recognize_end >= until:
            break


def recognize_income(until=None, dry_run=False):
    """
    Create all ``Transaction`` necessary to recognize revenue
    on each ``Subscription`` until date specified.
    """
    until = datetime_or_now(until)
    LOGGER.info("recognize income until %s ...", until)
    for subscription in Subscription.objects.filter(created_at__lte=until):
        # We need to pass through subscriptions otherwise we won't recognize
        # income on subscription that were just cancelled.
        try:
            with transaction.atomic():
                _recognize_subscription_income(subscription, until=until)
                if dry_run:
                    raise DryRun()
        except AssertionError as err:
            # We log the exception and moves on to the next subscription,
            # giving a chance to others to complete.
            LOGGER.exception(err)
        except DryRun:
            pass


def extend_subscriptions(at_time=None, dry_run=False):
    """
    Extend active subscriptions
    """
    at_time = datetime_or_now(at_time)
    LOGGER.info("extend subscriptions at %s ...", at_time)
    for subscription in Subscription.objects.filter(
            auto_renew=True, created_at__lte=at_time, ends_at__gt=at_time):
        lower, upper = subscription.clipped_period_for(at_time)
        LOGGER.debug("at_time (%s) in period [%s, %s[ of %s ending at %s",
            at_time, lower, upper, subscription, subscription.ends_at)
        days_from_end = relativedelta(subscription.ends_at, at_time).days
        if (upper == subscription.ends_at
            and (days_from_end >= 0 and days_from_end < 1)):
            # We are in the last day of the last period.
            LOGGER.info("EXTENDS subscription %s ending at %s for 1 period",
                subscription, subscription.ends_at)
            if not dry_run:
                try:
                    with transaction.atomic():
                        _ = Transaction.objects.record_order([
                            Transaction.objects.new_subscription_order(
                                subscription, 1, created_at=at_time)])
                except Exception as err: #pylint:disable=broad-except
                    # logs any kind of errors
                    # and move on to the next subscription.
                    LOGGER.exception(
                        "error: extending subscription for %s ending at %s: %s",
                        subscription, subscription.ends_at, err)


def trigger_expiration_notices(at_time=None, nb_days=15, dry_run=False):
    """
    Trigger a signal for all subscriptions which are near the expiration date.
    """
    at_time = datetime_or_now(at_time)
    lower = at_time + relativedelta(days=nb_days)
    upper = at_time + relativedelta(days=nb_days + 1)
    LOGGER.info(
        "trigger notifications for subscription expiring within [%s,%s[ ...",
        lower, upper)
    for subscription in Subscription.objects.filter(
            auto_renew=False, ends_at__gte=lower, ends_at__lt=upper,
            plan__auto_renew=True):
        LOGGER.info("trigger expires soon for %s", subscription)
        if not dry_run:
            signals.expires_soon.send(sender=__name__,
                subscription=subscription, nb_days=nb_days)


def create_charges_for_balance(until=None, dry_run=False):
    """
    Create charges for all accounts payable.
    """
    #pylint:disable=too-many-nested-blocks
    until = datetime_or_now(until)
    LOGGER.info("create charges for balance at %s ...", until)
    for organization in Organization.objects.all():
        charges = Charge.objects.in_progress_for_customer(organization)
        # We will create charges only when we have no charges
        # already in flight for this customer.
        if not charges.exists():
            invoiceables = Transaction.objects.get_invoiceables(
                organization, until=until)
            balance = sum_dest_amount(invoiceables)
            invoiceable_amount = balance['amount']
            if invoiceable_amount > 50:
                # Stripe will not processed charges less than 50 cents.
                if not Subscription.objects.active_for(
                        organization, ends_at=until).filter(
                        auto_renew=True).exists():
                    # If we have a past due but it is not coming from a renewal
                    # generated earlier, we will make a note of it but do not
                    # charge the Card. Each provider needs to decide what to do
                    # about collections.
                    LOGGER.info('REVIEW %dc to %s (requires manual charge)',
                        invoiceable_amount, organization)
                else:
                    LOGGER.info('CHARGE %dc to %s', invoiceable_amount,
                        organization)
                    try:
                        if not dry_run:
                            Charge.objects.charge_card(
                                organization, invoiceables)
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
