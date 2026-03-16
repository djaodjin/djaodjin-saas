# Copyright (c) 2026, DjaoDjin inc.
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

"""Command for the cron job. Send revenue report for the last week"""

import logging

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.template.defaultfilters import slugify
from rest_framework.settings import api_settings

from ... import humanize, settings, signals
from ...compat import force_str, six
from ...helpers import datetime_or_now
from ...metrics.base import generate_periods, usage_metrics
from ...metrics.transactions import revenue_metrics
from ...metrics.subscriptions import subscribers_metrics

from ...models import Plan
from ...utils import get_organization_model, parse_tz

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """Send past week revenue report in email"""
    help = 'Send past week revenue report in email'

    inverted_period_choices = {
        slugify(val): key for key, val in six.iteritems(
            dict(Plan.INTERVAL_CHOICES))}

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            dest='dry_run', default=False,
            help='Do not trigger the signal'
        )
        parser.add_argument(
            '--at-time', action='store',
            dest='at_time', default=None,
            help='Specifies the time at which the command runs'
        )
        parser.add_argument(
            '--provider', action='append',
            dest='providers', default=None,
            help='Specifies provider to generate reports for'
        )
        parser.add_argument(
            '--period', action='store',
            dest='period', default='weekly',
            choices=list(six.iterkeys(self.inverted_period_choices)),
            help='Specifies the period to generate reports for'
        )

    @staticmethod
    def construct_date_periods(at_time, period=humanize.WEEKLY, timezone=None):
        # discarding time, keeping utc tzinfo (00:00:00 utc)
        tzinfo = parse_tz(timezone)

        def localize_time(time):
            # we are interested in 00:00 local time, if we don't have
            # local time zone, fall back to 00:00 utc time
            # in case we have local timezone, replace utc with it
            return (tzinfo.localize(time.replace(tzinfo=None))
                if tzinfo else time)

        base_time = at_time.replace(
            minute=0 if period != humanize.YEARLY else at_time.minute,
            second=0,
            microsecond=0
        )

        base_time = localize_time(base_time)

        if not period:
            return None, None

        # 'yearly' is unique in its treatment of the starting date.
        # Flag set for special handling later.
        include_start = (period == humanize.YEARLY)

        # Calculate the date exactly one year, month, or day prior to base_time
        if period == humanize.HOURLY:
            prev_mirror_from_date = base_time - relativedelta(days=1)
        elif period == humanize.DAILY:
            prev_mirror_from_date = base_time - relativedelta(weeks=1)
        else:
            prev_mirror_from_date = base_time - relativedelta(years=1)

        # Logic for dealing with cases where it's the first day of the year
        if base_time.day == 1 and base_time.month == 1:
            prev_mirror_from_date -= relativedelta(years=1)
        # Generates the most recent two periods and the recent period
        # from a year ago using date-generating functions.
        prev_period = generate_periods(period, nb_periods=2,
            from_date=base_time, tzinfo=tzinfo,
            include_start_date=include_start)
        prev_mirror = generate_periods(period, nb_periods=1,
            from_date=prev_mirror_from_date, tzinfo=tzinfo,
            include_start_date=False)

        return prev_period, prev_mirror

    @staticmethod
    def construct_table(table, unit=None):
        def calculate_percentage_change(current, previous):
            try:
                amount = (current - previous) * 100 / previous
                percentage = str(round(amount, 2)) + '%'
                if amount > 0:
                    percentage = '+' + percentage
                return percentage
            except ZeroDivisionError:
                return 'N/A'

        for row in table:
            values = row['values']
            for idx in range(1, len(values)):
                values[idx][1] = calculate_percentage_change(
                    values[0][1], values[idx][1])
            if unit in (settings.DEFAULT_UNIT,):
                values[0][1] = humanize.as_money(values[0][1], unit)
            else:
                values[0][1] = str(values[0][1])
        return table

    @staticmethod
    def get_revenue_metrics(provider, prev_periods, prev_year_periods):
        """
        Returns revenue metrics
        """
        metrics = revenue_metrics(provider, prev_periods)
        mirror_metrics = revenue_metrics(provider, prev_year_periods)
        unit = metrics.get('unit')

        table = []
        mirror_results = mirror_metrics.get('results')
        for idx, entry in enumerate(metrics.get('results')):
            table += [{
                'slug': entry.get('slug'),
                'title': entry.get('title'),
                'values': [
                    ['last', entry['values'][1][1]],
                    ['prev', entry['values'][0][1]],
                    ['prev_year', mirror_results[idx]['values'][0][1]]
                ]}]

        return (table, unit)


    @staticmethod
    def get_subscribers_metrics(provider, prev_periods, prev_year_periods):
        """
        Returns subscribers metrics
        """
        metrics = subscribers_metrics(provider, prev_periods)
        mirror_metrics = subscribers_metrics(provider, prev_year_periods)
        unit = metrics.get('unit')

        table = []
        mirror_results = mirror_metrics.get('results')
        for idx, entry in enumerate(metrics.get('results')):
            table += [{
                'slug': entry.get('slug'),
                'title': entry.get('title'),
                'values': [
                    ['last', entry['values'][1][1]],
                    ['prev', entry['values'][0][1]],
                    ['prev_year', mirror_results[idx]['values'][0][1]]
                ]}]

        return (table, unit)


    @staticmethod
    def get_usage_metrics(provider, prev_periods, prev_year_periods):
        """
        Returns usage metrics
        """
        if not provider.is_broker:
            # We report registered users and created profiles only
            # for the broker account.
            return ([], None)

        metrics = usage_metrics(prev_periods)
        mirror_metrics = usage_metrics(prev_year_periods)
        unit = metrics.get('unit')

        table = []
        mirror_results = mirror_metrics.get('results')
        for idx, entry in enumerate(metrics.get('results')):
            table += [{
                'slug': entry.get('slug'),
                'title': entry.get('title'),
                'values': [
                    ['last', entry['values'][1][1]],
                    ['prev', entry['values'][0][1]],
                    ['prev_year', mirror_results[idx]['values'][0][1]]
                ]}]

        return (table, unit)


    def handle(self, *args, **options):
        #pylint:disable=too-many-locals
        # aware utc datetime object
        at_time = datetime_or_now(options.get('at_time'))
        dry_run = options['dry_run']
        period_type = self.inverted_period_choices[options.get('period')]
        period_name = humanize.describe_period_name(period_type, 1)

        self.stdout.write(
            "running report_weekly_revenue for %s %s period at %s" %
            ('an' if period_type == humanize.HOURLY else 'a',
             period_name, at_time))

        providers = get_organization_model().objects.filter(is_provider=True)
        provider_slugs = options.get('providers')
        if provider_slugs:
            providers = providers.filter(slug__in=provider_slugs)
        for provider in providers:
            self.run_report(provider, at_time, period_type, dry_run=dry_run)


    def run_report(self, provider, at_time, period_type=humanize.WEEKLY,
                   dry_run=False):
        # pylint:disable=too-many-locals
        period_name = humanize.describe_period_name(period_type, 1)
        dates = self.construct_date_periods(
            at_time, period=period_type, timezone=provider.default_timezone)
        prev_period, prev_year = dates
        LOGGER.debug(
            "Two last consecutive %ss\n: %s to %s and %s to %s",
            period_name,
            prev_period[0].isoformat(), prev_period[1].isoformat(),
            prev_period[1].isoformat(), prev_period[2].isoformat())
        mirror_period_name = humanize.describe_period_name(period_type + 1,
            1) if period_type < humanize.YEARLY else period_name
        curr_title = 'Last %s' % period_name
        prev_title = 'Prev %s' % period_name
        if period_type == humanize.YEARLY:
            curr_title = "YTD"
            prev_title = str(prev_period[0].year)
            mirror_title = str(prev_year[0].year)
            LOGGER.debug(
                "Year before the corresponding yearly period\n: %s to %s",
                prev_year[0].isoformat(), prev_year[1].isoformat())
        elif period_type == humanize.HOURLY:
            mirror_title = "Same %s yesterday" % period_name
            LOGGER.debug(
                "Same %s from the previous %s\n: %s to %s",
                period_name, mirror_period_name,
                prev_year[0].isoformat(), prev_year[1].isoformat())
        elif period_type == humanize.DAILY:
            mirror_title = "Same %s last %s" % (period_name, mirror_period_name)
            LOGGER.debug(
                "Same %s from the previous %s\n: %s to %s",
                period_name, mirror_period_name,
                prev_year[0].isoformat(), prev_year[1].isoformat())
        else:
            mirror_title = "Same %s last year" % period_name
            LOGGER.debug(
                "Same %s from the previous year\n: %s to %s",
                period_name,
                prev_year[0].isoformat(), prev_year[1].isoformat())

        data, unit = self.get_revenue_metrics(provider, prev_period, prev_year)
        table = self.construct_table(data, unit)

        data, unit = self.get_subscribers_metrics(
            provider, prev_period, prev_year)
        table += self.construct_table(data, unit)

        data, unit = self.get_usage_metrics(provider, prev_period, prev_year)
        table += self.construct_table(data, unit)

        self.stdout.write("{0:<21s} | {1:>12s} | {2:>9s} | {3:>9s}".format(
            str(provider), curr_title, prev_title, mirror_title))
        for row in table:
            self.stdout.write(
                "  {0:<19s} | {1:>12s} | {2:>9s} | {3:>9s}".format(
                force_str(row['title']),  # It could be a translation object.
                row['values'][0][1],
                row['values'][1][1],
                row['values'][2][1]))

        # XXX details new users and profiles
        period_start = prev_period[1]
        period_end = prev_period[2]

        new_users_sampled = None
        nb_additional_new_users = 0
        new_profiles_sampled = None
        nb_additional_new_profiles = 0
        if provider.is_broker:
            queryset = get_user_model().objects.filter(
                date_joined__gte=period_start, date_joined__lt=period_end)
            count = queryset.count()
            if count:
                self.stdout.write("New users %s" % curr_title)
                new_users_sampled = queryset.order_by(
                        'date_joined')[:api_settings.PAGE_SIZE]
                for user in new_users_sampled :
                    self.stdout.write(
                        "  - %(created_at)s,\"%(full_name)s\",\"%(email)s\"" % {
                        'created_at': user.date_joined.isoformat(),
                        'full_name': user.get_full_name(),
                        'email': user.email if user.email else ""})
                if count > api_settings.PAGE_SIZE:
                    nb_additional_new_users = (
                        count - api_settings.PAGE_SIZE)
                    self.stdout.write("... (%d more)" % nb_additional_new_users)

            queryset = get_organization_model().objects.find_created_between(
                period_start, period_end)
            count = queryset.count()
            if count:
                self.stdout.write("New profiles %s" % curr_title)
                new_profiles_sampled = queryset.order_by(
                        'created_at')[:api_settings.PAGE_SIZE]
                for profile in new_profiles_sampled:
                    self.stdout.write(
                        "  - %(created_at)s,\"%(full_name)s\",\"%(email)s\"" % {
                        'created_at': profile.created_at.isoformat(),
                        'full_name': profile.full_name,
                        'email': profile.email if profile.email else ""})
                if count > api_settings.PAGE_SIZE:
                    nb_additional_new_profiles = (
                        count - api_settings.PAGE_SIZE)
                    self.stdout.write(
                        "... (%d more)" % nb_additional_new_profiles)

        if not dry_run:
            signals.period_sales_report_created.send(sender=__name__,
                provider=provider, dates=dates, data=table,
                new_users_sampled=new_users_sampled,
                nb_additional_new_users=nb_additional_new_users,
                new_profiles_sampled=new_profiles_sampled,
                nb_additional_new_profiles=nb_additional_new_profiles)
