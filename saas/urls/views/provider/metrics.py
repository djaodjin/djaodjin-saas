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
Urls to metrics
"""

from .... import settings
from ....compat import path
from ....views.download import CartItemDownloadView
from ....views.profile import DashboardView
from ....views.metrics import (SubscribersActivityView,
    CouponMetricsView, LifeTimeValueDownloadView,
    LifeTimeValueMetricsView, PlansMetricsView, RevenueMetricsView)


urlpatterns = [
    path('metrics/<slug:%s>/coupons/download' %
        settings.PROFILE_URL_KWARG,
        CartItemDownloadView.as_view(),
        name='saas_metrics_coupons_download'),
    path('metrics/<slug:%s>/coupons/<slug:coupon>/download' %
        settings.PROFILE_URL_KWARG,
        CartItemDownloadView.as_view(), name='saas_coupon_uses_download'),
    path('metrics/<slug:%s>/coupons/<slug:coupon>/' %
        settings.PROFILE_URL_KWARG,
        CouponMetricsView.as_view(), name='saas_metrics_coupon'),
    path('metrics/<slug:%s>/coupons/' %
        settings.PROFILE_URL_KWARG,
        CouponMetricsView.as_view(), name='saas_metrics_coupons'),
    path('metrics/<slug:%s>/dashboard/' %
        settings.PROFILE_URL_KWARG,
        DashboardView.as_view(), name='saas_dashboard'),
    path('metrics/<slug:%s>/revenue/' %
        settings.PROFILE_URL_KWARG,
        RevenueMetricsView.as_view(), name='saas_metrics_summary'),
    path('metrics/<slug:%s>/plans/' %
        settings.PROFILE_URL_KWARG,
        PlansMetricsView.as_view(), name='saas_metrics_plans'),
    path('metrics/<slug:%s>/lifetimevalue/download' %
        settings.PROFILE_URL_KWARG,
        LifeTimeValueDownloadView.as_view(),
        name='saas_metrics_lifetimevalue_download'),
    path('metrics/<slug:%s>/lifetimevalue/' %
        settings.PROFILE_URL_KWARG,
        LifeTimeValueMetricsView.as_view(), name='saas_metrics_lifetimevalue'),
    path('metrics/<slug:%s>/activity/' %
        settings.PROFILE_URL_KWARG,
        SubscribersActivityView.as_view(),
        name='saas_subscribers_activity'),
]
