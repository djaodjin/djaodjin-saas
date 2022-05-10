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

'''Urls to metrics'''

from ... import settings
from ...compat import re_path
from ...views.download import CartItemDownloadView
from ...views.profile import DashboardView
from ...views.metrics import (SubscribersActivityView,
    CouponMetricsView, LifeTimeValueDownloadView,
    LifeTimeValueMetricsView, PlansMetricsView, RevenueMetricsView)


urlpatterns = [
    re_path(r'^metrics/(?P<organization>%s)/coupons/download/?' %
        settings.SLUG_RE, CartItemDownloadView.as_view(),
        name='saas_metrics_coupons_download'),
    re_path(r'^metrics/(?P<organization>%s)/coupons/(?P<coupon>%s)/download/?'
        % (settings.SLUG_RE, settings.SLUG_RE),
        CartItemDownloadView.as_view(), name='saas_coupon_uses_download'),
    re_path(r'^metrics/(?P<organization>%s)/coupons/((?P<coupon>%s)/)?'
        % (settings.SLUG_RE, settings.SLUG_RE),
        CouponMetricsView.as_view(), name='saas_metrics_coupons'),
    re_path(r'^metrics/(?P<organization>%s)/dashboard/' % settings.SLUG_RE,
        DashboardView.as_view(), name='saas_dashboard'),
    re_path(r'^metrics/(?P<organization>%s)/revenue/' % settings.SLUG_RE,
        RevenueMetricsView.as_view(), name='saas_metrics_summary'),
    re_path(r'^metrics/(?P<organization>%s)/plans/' % settings.SLUG_RE,
        PlansMetricsView.as_view(), name='saas_metrics_plans'),
    re_path(r'^metrics/(?P<organization>%s)/lifetimevalue/download/?' %
        settings.SLUG_RE, LifeTimeValueDownloadView.as_view(),
        name='saas_metrics_lifetimevalue_download'),
    re_path(r'^metrics/(?P<organization>%s)/lifetimevalue/' % settings.SLUG_RE,
        LifeTimeValueMetricsView.as_view(), name='saas_metrics_lifetimevalue'),
    re_path(r'metrics/(?P<organization>%s)/activity/' % settings.SLUG_RE,
        SubscribersActivityView.as_view(),
        name='saas_subscribers_activity'),
]
