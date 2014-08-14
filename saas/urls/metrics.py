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

'''Urls to metrics'''

from django.conf.urls import patterns, url

from saas.settings import ACCT_REGEX
from saas.views.metrics import (CouponMetricsView,
    PlansMetricsView, RevenueMetricsView, UsageMetricsView)

urlpatterns = patterns(
    'saas.views.metrics',
    url(r'^usage/', UsageMetricsView.as_view(), name='saas_organization_usage'),
    url(r'^plans/((?P<from_date>\d\d\d\d-\d\d)/)?',
        PlansMetricsView.as_view(), name='saas_metrics_plans'),
    url(r'^coupons/((?P<coupon>%s)/)?' % ACCT_REGEX,
        CouponMetricsView.as_view(), name='saas_metrics_coupons'),
    url(r'^((?P<from_date>\d\d\d\d-\d\d))?',
        RevenueMetricsView.as_view(), name='saas_metrics_summary'),
)
