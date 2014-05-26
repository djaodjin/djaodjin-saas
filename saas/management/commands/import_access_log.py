# Copyright (c) 2014, DjaoDjin inc.
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
Command for the cron job. Daily visitors
"""

import datetime, logging, re, time

from django.core.management.base import BaseCommand

from saas.models import NewVisitors

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "Save new vistor datas into the database."\
" This command needs the path of the log file to analyse."

    def handle(self, args, **options):
        #pylint: disable=too-many-locals
        for arg in args:
            with open(arg) as log:
                visitors = []
                # delete all bots
                excludes = ["bot", "Pub", "Spider", "spider", "AhrefsBot"]
                for line in log.readlines():
                    if not re.match(r'.*(%s).*' % '|'.join(excludes), line):
                        visitors += [line]

                # create a dictionnary of IP, browser per date
                browser = []
                for line in visitors:
                    look = re.match(
r'(?P<ip_addr>\S+) - - \[(?P<date>.*)\].*"(?<browser>.+)" ".+"', line)
                    if look:
                        browser += [{"IP": look.group('ip_addr'),
                            "browser": look.group('browser'),
                            "date": datetime.datetime.strftime(
                                datetime.datetime.fromtimestamp(time.mktime(
                                time.strptime(look.group('date'), "%d/%b/%Y"))),
                                    "%Y/%m/%d")}]

                # all dates per visitors
                dates_per_unique_visitor = {}
                for datas in browser:
                    key = (datas["IP"], datas["browser"])
                    if not key in dates_per_unique_visitor:
                        dates_per_unique_visitor[key] = []
                    dates_per_unique_visitor[key] += [datas["date"]]

                final_list = {}
                for itu in dates_per_unique_visitor:
                    key = dates_per_unique_visitor[itu][0]
                    if not key in final_list:
                        final_list[key] = []
                    final_list[key] += [itu]

                for item in sorted(final_list.items()):
                    # check in database if the date exists and if not save into
                    # the database
                    NewVisitors.objects.get_or_create(
                        date=datetime.datetime.strftime(
                            datetime.datetime.fromtimestamp(time.mktime(
                            time.strptime(item[0], "%Y/%m/%d"))), "%Y-%m-%d"),
                        visitors_number=len(item[1]))

