# Copyright (c) 2022, DjaoDjin inc.
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

from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.db import transaction

from . import humanize, settings, signals
from .backends import CardError, ProcessorError
from .compat import gettext_lazy as _, six
from .models import (Charge, Plan, Price, Subscription, Transaction,
    sum_dest_amount, get_period_usage, get_sub_event_id)
from .utils import datetime_or_now, get_organization_model

LOGGER = logging.getLogger(__name__)


class DryRun(RuntimeError):

    pass


def _recognize_subscription_income(subscription, until=None):
    #pylint:disable=too-many-locals,too-many-statements
    until = datetime_or_now(until)
    # [``recognize_start``, ``recognize_end``[ is one period over which
    # revenue is recognized. It will slide over the subscription
    # lifetime from ``created_at`` to ``until``.
    order_subscribe_beg = subscription.created_at
    recognize_period_idx = 0
    recognize_start = subscription.created_at
    recognize_end = (subscription.created_at
        + relativedelta(months=recognize_period_idx + 1))
    LOGGER.debug('process subscription %d %s', subscription.id, subscription)
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
        LOGGER.debug('\tprocess transaction %d %s of %dc covering [%s, %s['\
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
                    if subscription.plan.period_type > Plan.DAILY:
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

            # recognizing use charges for subscription
            use_charges = subscription.plan.use_charges.all()
            for use_charge in use_charges:
                quantity = get_period_usage(subscription, use_charge,
                    recognize_start, recognize_end)
                extra = quantity - use_charge.quota
                to_recognize_amount = 0
                if extra > 0:
                    to_recognize_amount = extra * use_charge.use_amount

                balance = Transaction.objects.get_use_charge_balance(
                    subscription, use_charge, recognize_start, recognize_end)
                recognized_amount = balance['amount']
                recognized_amount = abs(recognized_amount)

                if to_recognize_amount > recognized_amount:
                    amount = to_recognize_amount - recognized_amount
                    event_id = get_sub_event_id(subscription, use_charge)

                    # creating a liability for a customer
                    Transaction.objects.create(
                        event_id=event_id,
                        created_at=recognize_end - relativedelta(seconds=1),
                        descr=humanize.DESCRIBE_DOUBLE_ENTRY_MATCH,
                        dest_unit=subscription.plan.unit,
                        dest_amount=amount,
                        dest_account=Transaction.LIABILITY,
                        dest_organization=subscription.organization,
                        orig_unit=subscription.plan.unit,
                        orig_amount=amount,
                        orig_account=Transaction.PAYABLE,
                        orig_organization=subscription.organization)

                    # recognizing an income for a provider
                    descr = humanize.DESCRIBE_RECOGNIZE_INCOME % {
                        'subscription': use_charge,
                        'period_start': recognize_start,
                        'period_end': recognize_end
                    }
                    Transaction.objects.create_income_recognized(
                        subscription, amount=amount, event_id=event_id,
                        starts_at=recognize_start, ends_at=recognize_end,
                        descr=descr)

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
    for subscription in Subscription.objects.valid_for(created_at__lte=until):
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
    for subscription in Subscription.objects.valid_for(
            auto_renew=True, created_at__lte=at_time, ends_at__gt=at_time):
        lower, upper = subscription.clipped_period_for(at_time)
        # `relativedelta` will compute number of years, months, days, etc.
        # `days` represents the difference in days after years and months have
        # been substracted instead of a total number of days as `timedelta`
        # does.
        days_from_end = (subscription.ends_at - at_time).days
        LOGGER.debug("at_time (%s) in period [%s, %s[ of %s ending at %s,"
            " %d days from renewal", at_time, lower, upper, subscription,
            subscription.ends_at, days_from_end)
        if (upper == subscription.ends_at
            and (days_from_end >= 0 and days_from_end < 1)):
            # We are in the last day of the last period.
            LOGGER.info("EXTENDS subscription %s ending at %s for 1 period",
                subscription, subscription.ends_at)
            if not dry_run:
                try:
                    with transaction.atomic():
                        Transaction.objects.record_order([
                            Transaction.objects.new_subscription_order(
                                subscription, created_at=at_time)])
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

    def _handle_organization_notices(organization):
        if organization.processor_card_key:
            card = organization.retrieve_card()
            try:
                exp_month, exp_year = card['exp_date'].split('/')
                exp_date = datetime(year=int(exp_year),
                    month=int(exp_month), day=1, tzinfo=at_time.tzinfo)
                if lower >= exp_date:
                    LOGGER.info("payment method expires soon for %s",
                        organization)
                    if not dry_run:
                        signals.card_expires_soon.send(
                            sender=__name__, organization=organization,
                            nb_days=nb_days)
            except (KeyError, ValueError):
                # exp info is missing or the format is incorrect
                pass
        else:
            LOGGER.info("%s doesn't have a payment method attached",
                organization)
            if not dry_run:
                signals.payment_method_absent.send(sender=__name__,
                    organization=organization)

    at_time = datetime_or_now(at_time)
    lower = at_time + relativedelta(days=nb_days)
    upper = at_time + relativedelta(days=nb_days + 1)
    LOGGER.info(
        "trigger notifications for subscription expiring within [%s,%s[ ...",
        lower, upper)
    prev_organization = None
    subscription = None
    for subscription in Subscription.objects.valid_for(ends_at__gte=lower,
            ends_at__lt=upper).order_by('organization'):
        org = subscription.organization
        plan = subscription.plan

        try:
            if subscription.auto_renew:
                if plan.renewal_type == plan.AUTO_RENEW:
                    if org.id != prev_organization:
                        _handle_organization_notices(org)

                    prev_organization = org.id
            else:
                if plan.renewal_type == plan.ONE_TIME:
                    LOGGER.info("trigger upgrade soon for %s", subscription)
                    if not dry_run:
                        signals.subscription_upgrade.send(sender=__name__,
                            subscription=subscription, nb_days=nb_days)

                elif plan.renewal_type == plan.REPEAT:
                    LOGGER.info("trigger expires soon for %s", subscription)
                    if not dry_run:
                        signals.expires_soon.send(sender=__name__,
                            subscription=subscription, nb_days=nb_days)

        except Exception as err: #pylint:disable=broad-except
            # We use `Exception` because the email server might be
            # unavailable but ConnectionRefusedError is not a subclass
            # of RuntimeError.
            LOGGER.exception("error: %s", err)

    # flushing the last organization
    if subscription and subscription.organization.id != prev_organization:
        if subscription.auto_renew:
            if subscription.plan.renewal_type == subscription.plan.AUTO_RENEW:
                _handle_organization_notices(subscription.organization)


def create_charges_for_balance(until=None, dry_run=False):
    """
    Create charges for all accounts payable.
    """
    #pylint:disable=too-many-nested-blocks
    until = datetime_or_now(until)
    LOGGER.info("create charges for balance at %s ...", until)
    for organization in get_organization_model().objects.filter(
            nb_renewal_attempts__lt=settings.MAX_RENEWAL_ATTEMPTS):
        charges = Charge.objects.in_progress_for_customer(organization)
        # We will create charges only when we have no charges
        # already in flight for this customer.
        if not charges.exists():
            invoiceables = Transaction.objects.get_invoiceables(
                organization, until=until)
            LOGGER.debug("invoicables for %s until %s:", organization, until)
            for invoicable in invoiceables:
                LOGGER.debug("\t#%d %s %s", invoicable.pk,
                    invoicable.dest_amount, invoicable.dest_unit)
            balances = sum_dest_amount(invoiceables)
            if len(balances) > 1:
                raise ValueError("balances with multiple currency units (%s)" %
                    str(balances))
            # `sum_dest_amount` guarentees at least one result.
            invoiceable_amount = balances[0]['amount']
            invoiceable_unit = balances[0]['unit']
            if invoiceable_amount > 50:
                # Stripe will not processed charges less than 50 cents.
                active_subscriptions = Subscription.objects.active_for(
                    organization, ends_at=until).filter(auto_renew=True)
                if not active_subscriptions.exists():
                    # If we have a past due but it is not coming from a renewal
                    # generated earlier, we will make a note of it but do not
                    # charge the Card. Each provider needs to decide what to do
                    # about collections.
                    LOGGER.info('REVIEW %d %s to %s (requires manual charge)',
                        invoiceable_amount, invoiceable_unit, organization)
                else:
                    try:
                        if not organization.processor_card_key:
                            raise CardError(_("No payment method attached"),
                                'card_absent')
                        if not dry_run:
                            Charge.objects.charge_card(
                                organization, invoiceables,
                                created_at=until)
                        LOGGER.info('CHARGE %d %s to %s',
                            invoiceable_amount, invoiceable_unit,
                            organization)
                    except CardError as err:
                        # There was a problem with the Card (i.e. expired,
                        # underfunded, etc.)
                        charge_processor_key = getattr(
                            err, 'charge_processor_key', None)
                        LOGGER.info('FAILED CHARGE %d %s to %s (%s: %s)',
                            invoiceable_amount, invoiceable_unit,
                            organization.slug, charge_processor_key,
                            err, extra={
                                'event': 'card-error',
                                'charge': charge_processor_key,
                                'detail': err.processor_details(),
                                'organization': organization.slug,
                                'amount': invoiceable_amount,
                                'unit': invoiceable_unit})
                        organization.nb_renewal_attempts = (
                            organization.nb_renewal_attempts + 1)
                        final_notice = False
                        if (organization.nb_renewal_attempts >=
                            settings.MAX_RENEWAL_ATTEMPTS):
                            final_notice = True
                            if not dry_run:
                                active_subscriptions.unsubscribe(at_time=until)
                        if not dry_run:
                            organization.save()
                        signals.renewal_charge_failed.send(
                            sender=__name__,
                            invoiced_items=invoiceables,
                            total_price=Price(
                                invoiceable_amount, invoiceable_unit),
                            final_notice=final_notice)
                    except ProcessorError as err:
                        # An error from the processor which indicates
                        # the logic might be incorrect, the network down,
                        # etc. We have already notified the admin
                        # in `charge_card_one_processor`.
                        pass
            elif invoiceable_amount > 0:
                LOGGER.info('SKIP   %d %s to %s (less than 50 %s)',
                    invoiceable_amount, invoiceable_unit, organization,
                    invoiceable_unit)
        else:
            LOGGER.info('SKIP   %s (one charge already in flight)',
                organization)


def complete_charges():
    """
    Update the state of all charges in progress.
    """
    for charge in Charge.objects.filter(state=Charge.CREATED):
        charge.retrieve()
