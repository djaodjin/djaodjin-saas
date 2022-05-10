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
URLs API for provider resources related to billing
"""

from .... import settings
from ....api.federations import (FederatedSubscribersAPIView,
    SharedProfilesAPIView)
from ....api.metrics import (BalancesAPIView, CouponUsesAPIView,
    CustomerMetricAPIView, LifetimeValueMetricAPIView, PlanMetricAPIView,
    RevenueMetricAPIView)
from ....api.subscriptions import (ActiveSubscriptionAPIView,
    ChurnedSubscriptionAPIView)
from ....compat import re_path


urlpatterns = [
    re_path(r'^metrics/(?P<organization>%s)/coupons/(?P<coupon>%s)/?' % (
        settings.SLUG_RE, settings.SLUG_RE), CouponUsesAPIView.as_view(),
        name='saas_api_coupon_uses'),
    re_path(r'^metrics/(?P<organization>%s)/active/?' % settings.SLUG_RE,
        ActiveSubscriptionAPIView.as_view(), name='saas_api_subscribed'),
    re_path(r'^metrics/(?P<organization>%s)/balances/?' % settings.SLUG_RE,
        BalancesAPIView.as_view(), name='saas_api_balances'),
    re_path(r'^metrics/(?P<organization>%s)/churned/?' % settings.SLUG_RE,
        ChurnedSubscriptionAPIView.as_view(), name='saas_api_churned'),
    re_path(r'^metrics/(?P<organization>%s)/customers/?' % settings.SLUG_RE,
        CustomerMetricAPIView.as_view(), name='saas_api_customer'),
    re_path(r'^metrics/(?P<organization>%s)/plans/?' % settings.SLUG_RE,
        PlanMetricAPIView.as_view(), name='saas_api_metrics_plans'),
    re_path(r'^metrics/(?P<organization>%s)/funds/?' % settings.SLUG_RE,
        RevenueMetricAPIView.as_view(), name='saas_api_revenue'),
    re_path(r'^metrics/(?P<organization>%s)/lifetimevalue/?' % settings.SLUG_RE,
        LifetimeValueMetricAPIView.as_view(),
        name='saas_api_metrics_lifetimevalue'),

    # Metrics for a federation of providers
    re_path(r'metrics/(?P<organization>%s)/federated/shared/?' %
        settings.SLUG_RE, SharedProfilesAPIView.as_view(),
        name="saas_api_shared_profiles"),
    re_path(r'metrics/(?P<organization>%s)/federated/?' % settings.SLUG_RE,
        FederatedSubscribersAPIView.as_view(),
        name="saas_api_federated_subscribers"),
]
