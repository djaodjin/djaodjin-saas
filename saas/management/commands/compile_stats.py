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

"""Command for the cron job. Daily statistics"""

import datetime

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from saas.utils import get_organization_model


class Command(BaseCommand):
    """Daily usage for the service"""
    help = 'Print daily usage'

    def handle(self, *args, **options):
        end_period = datetime.datetime.now()
        start_period = end_period - datetime.timedelta(days=30)
        self.stdout.write('from %s to %s\n' % (start_period, end_period))
        for user in get_user_model().objects.filter(
            date_joined__gt=start_period):
            self.stdout.write('%s %s %s\n' % (str(user.date_joined),
                user.username, user.email))

        self.stdout.write('\n')
        for organization in get_organization_model().objects.filter(
            created_at__gt=start_period):
            self.stdout.write('%s %s\n'
                % (organization.created_at, organization))
