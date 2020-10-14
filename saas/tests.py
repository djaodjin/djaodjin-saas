# Copyright (c) 2018, DjaoDjin inc.
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

from django.test import TestCase

from .metrics.base import month_periods


class SaasTests(TestCase):
    """
    Tests saas innner functions
    """

    def test_month_periods_utc(self):
        """
        Test UTC datetime with no timezone
        """
        results = month_periods(from_date="2018-04-18T00:00:00+00:00")
        results = [str(res) for res in results]
        self.assertEqual(results, [
            '2017-05-01 00:00:00+00:00',
            '2017-06-01 00:00:00+00:00',
            '2017-07-01 00:00:00+00:00',
            '2017-08-01 00:00:00+00:00',
            '2017-09-01 00:00:00+00:00',
            '2017-10-01 00:00:00+00:00',
            '2017-11-01 00:00:00+00:00',
            '2017-12-01 00:00:00+00:00',
            '2018-01-01 00:00:00+00:00',
            '2018-02-01 00:00:00+00:00',
            '2018-03-01 00:00:00+00:00',
            '2018-04-01 00:00:00+00:00',
            '2018-04-18 00:00:00+00:00'])


    def test_month_periods_neg_offset(self):
        """
        Test datetime with negative timeoffset and no timezone
        """
        results = month_periods(from_date="2018-04-18T00:00:00-07:00")
        results = [str(res) for res in results]
        self.assertEqual(results, [
            '2017-05-01 00:00:00-07:00',
            '2017-06-01 00:00:00-07:00',
            '2017-07-01 00:00:00-07:00',
            '2017-08-01 00:00:00-07:00',
            '2017-09-01 00:00:00-07:00',
            '2017-10-01 00:00:00-07:00',
            '2017-11-01 00:00:00-07:00',
            '2017-12-01 00:00:00-07:00',
            '2018-01-01 00:00:00-07:00',
            '2018-02-01 00:00:00-07:00',
            '2018-03-01 00:00:00-07:00',
            '2018-04-01 00:00:00-07:00',
            '2018-04-18 00:00:00-07:00'])


    def test_month_periods_pos_offset(self):
        """
        Test datetime with positive timeoffset and no timezone
        """
        results = month_periods(from_date="2018-04-18T00:00:00+03:00")
        results = [str(res) for res in results]
        self.assertEqual(results, [
            '2017-05-01 00:00:00+03:00',
            '2017-06-01 00:00:00+03:00',
            '2017-07-01 00:00:00+03:00',
            '2017-08-01 00:00:00+03:00',
            '2017-09-01 00:00:00+03:00',
            '2017-10-01 00:00:00+03:00',
            '2017-11-01 00:00:00+03:00',
            '2017-12-01 00:00:00+03:00',
            '2018-01-01 00:00:00+03:00',
            '2018-02-01 00:00:00+03:00',
            '2018-03-01 00:00:00+03:00',
            '2018-04-01 00:00:00+03:00',
            '2018-04-18 00:00:00+03:00'])


    def test_month_periods_timezone(self):
        """
        Test datetime with a timezone
        """
        results = month_periods(from_date="2018-04-18T00:00:00-04:00",
            tz="US/Eastern")
        results = [str(res) for res in results]
        self.assertEqual(results, [
            '2017-05-01 00:00:00-04:00',
            '2017-06-01 00:00:00-04:00',
            '2017-07-01 00:00:00-04:00',
            '2017-08-01 00:00:00-04:00',
            '2017-09-01 00:00:00-04:00',
            '2017-10-01 00:00:00-04:00',
            '2017-11-01 00:00:00-04:00',
            '2017-12-01 00:00:00-05:00',
            '2018-01-01 00:00:00-05:00',
            '2018-02-01 00:00:00-05:00',
            '2018-03-01 00:00:00-05:00',
            '2018-04-01 00:00:00-04:00',
            '2018-04-18 00:00:00-04:00'])
