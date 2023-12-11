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
    RevenueMetricAPIView, BalancesDueAPIView, BalancesDownloadView,
    RevenueDownloadView, CouponUsesDownloadView, CustomerMetricDownloadView,
    LifetimeValueDownloadView, PlanMetricDownloadView, BalancesDueDownloadView)
from ....compat import path


urlpatterns = [
    path('metrics/<slug:%s>/coupons/<slug:coupon>' %
        settings.PROFILE_URL_KWARG,
        CouponUsesAPIView.as_view(), name='saas_api_coupon_uses'),
    path('metrics/<slug:%s>/balances' %
        settings.PROFILE_URL_KWARG,
        BalancesAPIView.as_view(), name='saas_api_balances'),
    path('metrics/<slug:%s>/customers' %
        settings.PROFILE_URL_KWARG,
        CustomerMetricAPIView.as_view(), name='saas_api_customer'),
    path('metrics/<slug:%s>/plans' %
        settings.PROFILE_URL_KWARG,
        PlanMetricAPIView.as_view(), name='saas_api_metrics_plans'),
    path('metrics/<slug:%s>/funds' %
        settings.PROFILE_URL_KWARG,
        RevenueMetricAPIView.as_view(), name='saas_api_revenue'),
    path('metrics/<slug:%s>/lifetimevalue' %
        settings.PROFILE_URL_KWARG,
        LifetimeValueMetricAPIView.as_view(),
        name='saas_api_metrics_lifetimevalue'),
    path('metrics/<slug:%s>/balances-due' %
         settings.PROFILE_URL_KWARG,
         BalancesDueAPIView.as_view(),
         name='saas_api_metrics_balances_due'),

    # Metrics for a federation of providers
    path('metrics/<slug:%s>/federated/shared' %
        settings.PROFILE_URL_KWARG,
        SharedProfilesAPIView.as_view(),
        name="saas_api_shared_profiles"),
    path('metrics/<slug:%s>/federated' %
        settings.PROFILE_URL_KWARG,
        FederatedSubscribersAPIView.as_view(),
        name="saas_api_federated_subscribers"),

    # Download metrics as CSV files
    path('metrics/<slug:%s>/coupons/<slug:coupon>/download' %
         settings.PROFILE_URL_KWARG,
         CouponUsesDownloadView.as_view(),
         name='saas_api_coupon_uses_download'),
    path('metrics/<slug:%s>/balances/download' %
         settings.PROFILE_URL_KWARG,
         BalancesDownloadView.as_view(),
         name='saas_api_balances_download'),
    path('metrics/<slug:%s>/customers/download' %
         settings.PROFILE_URL_KWARG,
         CustomerMetricDownloadView.as_view(),
         name='saas_api_customer_download'),
    path('metrics/<slug:%s>/plans/download' %
         settings.PROFILE_URL_KWARG,
         PlanMetricDownloadView.as_view(),
         name='saas_api_metrics_plans_download'),
    path('metrics/cowork/funds/download',
         RevenueDownloadView.as_view(),
         name='saas_api_revenue_download'),
    path('metrics/<slug:%s>/lifetimevalue/download' %
         settings.PROFILE_URL_KWARG,
         LifetimeValueDownloadView.as_view(),
         name='saas_api_metrics_lifetimevalue_download'),
    path('metrics/<slug:%s>/balances-due/download' %
         settings.PROFILE_URL_KWARG,
         BalancesDueDownloadView.as_view(),
         name='saas_api_metrics_balances_due_download'),
]
