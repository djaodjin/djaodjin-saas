# Copyright (c) 2019, DjaoDjin inc.
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

"""Command for sending invites"""
import time

from django.core.management.base import BaseCommand
from django.db.models import Q

from ...models import Subscription
from ...utils import get_role_model
from ... import signals


class Command(BaseCommand):
    """
    Send invites for roles granted on organizations.
    """
    help = 'Send invites'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
            dest='dry_run', default=False,
            help='Execute all code statements but do not send e-mails')
        parser.add_argument(
            '--organization', action='append', dest='organizations',
            help="Send invite e-mails for roles associated to"\
            " *organization* slug")
        parser.add_argument(
            '--email', action='append', dest='email',
            help='Send invite for this email only')
        parser.add_argument(
            '--no-role-grants', action='store_true',
            dest='no_role_grants', default=False,
            help='Do not send invites which are for roles granted.')
        parser.add_argument(
            '--no-role-requests', action='store_true',
            dest='no_role_requests', default=False,
            help='Do not send invites which are for roles requested.')
        parser.add_argument(
            '--no-subscription-grants', action='store_true',
            dest='no_subscription_grants', default=False,
            help='Do not send invites which are for subscriptions granted.')
        parser.add_argument(
            '--no-subscription-requests', action='store_true',
            dest='no_subscription_requests', default=False,
            help='Do not send invites which are for subscriptions requested.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        emails = options.get('email')
        organizations = options.get('organizations')
        if not options['no_role_grants']:
            self.send_role_grants(organizations, emails, dry_run)
        if not options['no_role_requests']:
            self.send_role_requests(organizations, emails, dry_run)
        if not options['no_subscription_grants']:
            self.send_subscription_grants(organizations, emails, dry_run)
        if not options['no_subscription_requests']:
            self.send_subscription_requests(organizations, emails, dry_run)

    def send_role_grants(self, organizations=None, emails=None, dry_run=False):
        roles = get_role_model().objects.filter(grant_key__isnull=False)
        if organizations:
            roles = roles.filter(organization__slug__in=organizations)
        if emails:
            roles = roles.filter(user__email__in=emails)

        self.stdout.write("%ssending %d role grant invites..." % (
            "(dry run) " if dry_run else "", len(roles)))
        for role in roles:
            self.stdout.write("\t%s for %s" % (
                role.user.email, role.organization.full_name))
            if not dry_run:
                signals.role_grant_created.send(sender=__name__, role=role)

    def send_role_requests(self,
                           organizations=None, emails=None, dry_run=False):
        roles = get_role_model().objects.filter(request_key__isnull=False)
        if organizations:
            roles = roles.filter(organization__slug__in=organizations)
        if emails:
            roles = roles.filter(user__email__in=emails)

        self.stdout.write("%ssending %d role request invites..." % (
            "(dry run) " if dry_run else "", len(roles)))
        for role in roles:
            self.stdout.write("\t%s for %s" % (
                role.user.email, role.organization.full_name))
            if not dry_run:
                signals.role_request_created.send(sender=__name__, role=role)

    def send_subscription_grants(self,
                                organizations=None, emails=None, dry_run=False):
        kwargs = {}
        subscriptions = Subscription.objects.filter(grant_key__isnull=False)
        if organizations:
            subscriptions = subscriptions.filter(
                plan__organization__slug__in=organizations)
        if emails:
            kwargs.update({'emails': emails})
            subscriptions = subscriptions.filter(
                Q(organization__email__in=emails) |
                Q(organization__role__user__email__in=emails)).distinct()

        self.stdout.write("%ssending %d subscription grant invites..." % (
            "(dry run) " if dry_run else "", len(subscriptions)))
        for subscription in subscriptions:
            starts_at = time.monotonic()
            try:
                self.stdout.write("\t%s to %s" % (
                    subscription.organization.printable_name,
                    subscription.plan.organization.full_name))
                if not dry_run:
                    signals.subscription_grant_created.send(
                        sender=__name__, subscription=subscription, **kwargs)
            except Exception as err: #pylint:disable=broad-except
                self.stderr.write("error:%s:%s: %s" % (
                    subscription.organization.printable_name,
                    subscription.plan.organization.full_name,
                    err))
            # dealing with smtpd limit rate
            delta = time.monotonic() - starts_at
            if delta < 1.0:
                time.sleep(1.0 - delta)


    def send_subscription_requests(self,
                                organizations=None, emails=None, dry_run=False):
        kwargs = {}
        subscriptions = Subscription.objects.filter(request_key__isnull=False)
        if organizations:
            subscriptions = subscriptions.filter(
                plan__organization__slug__in=organizations)
        if emails:
            kwargs.update({'emails': emails})
            subscriptions = subscriptions.filter(
                Q(organization__email__in=emails) |
                Q(organization__role__user__email__in=emails)).distinct()

        self.stdout.write("%ssending %d subscription request invites..." % (
            "(dry run) " if dry_run else "", len(subscriptions)))
        for subscription in subscriptions:
            self.stdout.write("\t%s to %s" % (subscription.organization.email,
                subscription.plan.organization.full_name))
            if not dry_run:
                signals.subscription_request_created.send(
                    sender=__name__, subscription=subscription, **kwargs)
