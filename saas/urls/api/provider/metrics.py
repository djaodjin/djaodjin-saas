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

"""
URLs API for provider resources related to billing
"""

from django.conf.urls import url

from ....api.metrics import (BalancesAPIView, CouponUsesAPIView,
    CustomerMetricAPIView, PlanMetricAPIView, RevenueMetricAPIView)
from ....api.subscriptions import (ActiveSubscriptionAPIView,
    ChurnedSubscriptionAPIView)
from ....settings import ACCT_REGEX


urlpatterns = [
    url(r'^metrics/(?P<organization>%s)/coupons/(?P<coupon>%s)/?' % (
        ACCT_REGEX, ACCT_REGEX), CouponUsesAPIView.as_view(),
        name='saas_api_coupon_uses'),
    url(r'^metrics/(?P<organization>%s)/active/?' % ACCT_REGEX,
        ActiveSubscriptionAPIView.as_view(), name='saas_api_subscribed'),
    url(r'^metrics/(?P<organization>%s)/balances/?' % ACCT_REGEX,
        BalancesAPIView.as_view(), name='saas_api_balances'),
    url(r'^metrics/(?P<organization>%s)/churned/?' % ACCT_REGEX,
        ChurnedSubscriptionAPIView.as_view(), name='saas_api_churned'),
    url(r'^metrics/(?P<organization>%s)/customers/?' % ACCT_REGEX,
        CustomerMetricAPIView.as_view(), name='saas_api_customer'),
    url(r'^metrics/(?P<organization>%s)/plans/?' % ACCT_REGEX,
        PlanMetricAPIView.as_view(), name='saas_api_metrics_plans'),
    url(r'^metrics/(?P<organization>%s)/funds/?' % ACCT_REGEX,
        RevenueMetricAPIView.as_view(), name='saas_api_revenue'),
]
