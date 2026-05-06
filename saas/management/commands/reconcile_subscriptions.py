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

"""Command to synchronize database subscriptions with rows in a spreadsheet"""

import csv, logging
from collections import OrderedDict, namedtuple

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.template.defaultfilters import slugify
from django.utils.dateparse import parse_datetime
from rest_framework.settings import api_settings

from ... import humanize, settings, signals
from ...compat import force_str, six, timezone_or_utc
from ...helpers import datetime_or_now
from ...metrics.base import generate_periods, usage_metrics
from ...metrics.transactions import revenue_metrics
from ...metrics.subscriptions import subscribers_metrics

from ...models import Plan, Subscription
from ...utils import get_organization_model

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """Update subscriptions from a spreadsheet"""
    help = 'Synchronize subscriptions with a spreadsheet'

    profile_model = get_organization_model()
    plan_model = Plan

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            dest='dry_run', default=False,
            help='Do not commit updates'
        )
        parser.add_argument(
            '--expired-at', action='store',
            dest='expired_at', default=None,
            help='When active subscriptions that are not renewed shoul end.'
        )
        parser.add_argument(
            '--created-at', action='store',
            dest='created_at', default=None,
            help='When new subscriptions start (defaults to `expired_at`)'
        )
        parser.add_argument(
            '--ends-at', action='store',
            dest='ends_at', default=None,
            help='When new and updated subscriptions end (defaults to end of'\
            ' natural period for `created_at`)'
        )
        parser.add_argument(
            '--at-time', action='store',
            dest='at_time', default=None,
            help='Specifies the time at which the command runs'
        )
        parser.add_argument('filenames', nargs='+',
            help="spreadsheets with subscriptions")

    def handle(self, *args, **options):
        #pylint:disable=too-many-locals
        dry_run = options['dry_run']
        subscriptions = {}
        for filename in options['filenames']:
            if filename.endswith('.csv'):
                with open(filename) as file_d:
                    csv_file = csv.reader(file_d)
                    try:
                        # first row is column heading
                        csv_model = namedtuple('csv_model',
                            [slugify(name).replace('-', '_')
                             for name in next(csv_file)])
                    except StopIteration:
                        self.stderr.write("error: no record found in %s" %
                            str(filename))
                    for row in csv_file:
                        rec = csv_model._make(row)
                        candidates = self.profile_model.objects.find_candidates(
                            rec.profile_name, email=rec.email)
                        try:
                            profile = candidates.get()
                            if rec.profile_name != profile.full_name:
                                LOGGER.info("substitutes profile '%s' for '%s'",
                                profile.full_name, rec.profile_name)
                        except self.profile_model.DoesNotExist:
                            LOGGER.info("new profile '%s' <%s>" % (
                                rec.profile_name, rec.email))
                            profile = self.profile_model(
                                full_name=rec.profile_name, email=rec.email)
                        except self.profile_model.MultipleObjectsReturned:
                            self.stderr.write("error: cannot decide profile"\
                                " '%s' <%s> out of %s" % (rec.profile_name,
                                rec.email, ', '.join([
                                    "'%s'" % candidate.full_name
                                    for candidate in candidates])))

                        plan = self.plan_model.objects.get(title=rec.plan)
                        if plan.slug not in subscriptions:
                            subscriptions[plan.slug] = {}
                        subscriptions[plan.slug].update({profile.slug: rec})

        self.sync_subscriptions(subscriptions,
            expired_at=options['expired_at'], created_at=options['created_at'],
            ends_at=options['ends_at'])

    def sync_subscriptions(self, subscriptions,
                           expired_at=None, created_at=None, ends_at=None):
        """
        - `expired_at`: When active subscriptions that are not renewed should
          end.
        - `created_at`: When new subscriptions start (defaults to `expired_at`)
        - `ends_at`: When new and updated subscriptions end (defaults to end
          of natural period for `created_at`)
        """
        if not expired_at:
            expired_at = datetime_or_now()
        if not created_at:
            created_at = expired_at
        self.stdout.write("BEGIN;")
        for plan_slug, profiles in subscriptions.items():
            plan = Plan.objects.get(slug=plan_slug)
            expired = self.profile_model.objects.filter(
                subscriptions__plan__slug=plan_slug,
                subscriptions__ends_at__gte=expired_at).exclude(
                    slug__in=profiles)
            self.stdout.write("UPDATE saas_subscription"\
                " SET ends_at='%(expired_at)s' WHERE"\
                " ends_at >= '%(expired_at)s' AND"
                " plan_id=(SELECT id FROM saas_plan WHERE slug='%(plan)s') AND"\
                " organization_id IN (SELECT id FROM saas_organization"\
                " WHERE slug IN (%(profiles)s));" % {
                    'expired_at': expired_at,
                    'plan': plan_slug,
                    'profiles': ', '.join(["'%s'" % profile.slug
                        for profile in expired])
                })
            default_renew_ends_at = ends_at
            if not ends_at:
                default_renew_ends_at = plan.end_of_period(created_at)
            for profile, rec in profiles.items():
                renew_ends_at = default_renew_ends_at
                if rec.until:
                    renew_ends_at = datetime_or_now(rec.until)
                try:
                    subscription = Subscription.objects.get(
                        plan__slug=plan_slug,
                        organization__slug=profile,
                        ends_at__gt=expired_at)
                    self.stdout.write("UPDATE saas_subscription"\
                        " SET ends_at='%(ends_at)s' WHERE"\
                        " ends_at >= '%(expired_at)s' AND"\
                    " plan_id=(SELECT id FROM saas_plan WHERE slug='%(plan)s')"\
                    " AND organization_id=(SELECT id FROM saas_organization"\
                        " WHERE slug='%(profile)s');" % {
                            'expired_at': expired_at,
                            'ends_at': renew_ends_at,
                            'plan': plan_slug,
                            'profile': profile
                    })
                except Subscription.DoesNotExist:
                    try:
                        profile = self.profile_model.objects.get(slug=profile)
                    except self.profile_model.DoesNotExist:
                        self.stdout.write("INSERT INTO saas_organization"\
                            " (slug, full_name, email) VALUES"\
                            " ('%(slug)s', '%(full_name)s', '%(email)s');" % {
                                'slug': profile.slug,
                                'full_name': profile.full_name,
                                'email': profile.email
                        })
                    self.stdout.write("INSERT INTO saas_subscription"\
                        " (created_at, ends_at, plan_id, organization_id)"\
                        " VALUES ('%(created_at)s', '%(ends_at)s',"\
                        " (SELECT id FROM saas_plan WHERE slug='%(plan)s'),"\
            " (SELECT id FROM saas_organization WHERE slug='%(profile)s'));" % {
                        'created_at': created_at,
                        'ends_at': renew_ends_at,
                        'profile': str(profile),
                        'plan': plan_slug
                    })

        self.stdout.write("COMMIT;")
