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
Urls to download records
"""

from django.conf.urls import url

from ...settings import ACCT_REGEX
from ...views import ProviderRedirectView
from ...views.download import TransferDownloadView
from ...views.metrics import (BalancesDownloadView,
    CouponMetricsDownloadView, ActiveSubscriptionDownloadView,
    ChurnedSubscriptionDownloadView)


urlpatterns = [
    url(r'^download/subscribers/active/?',
        ProviderRedirectView.as_view(
            pattern_name='saas_subscriber_pipeline_download_subscribed'),
        name='saas_provider_subscriber_pipeline_download_subscribed'),
    url(r'^download/subscribers/churned/?',
        ProviderRedirectView.as_view(
            pattern_name='saas_subscriber_pipeline_download_churned'),
        name='saas_provider_subscriber_pipeline_download_churned'),
    url(r'^download/coupons/',
        ProviderRedirectView.as_view(
            pattern_name='saas_metrics_coupons_download'),
        name='saas_provider_metrics_coupons_download'),
    url(r'^download/balances/?',
        ProviderRedirectView.as_view(pattern_name='saas_balances_download'),
        name='saas_provider_balances_download'),
    url(r'^download/transfers/?',
        ProviderRedirectView.as_view(pattern_name='saas_transfers_download'),
        name='saas_provider_transfers_download'),

    url(r'^download/(?P<organization>%s)/subscribers/active/?' % ACCT_REGEX,
        ActiveSubscriptionDownloadView.as_view(),
        name='saas_subscriber_pipeline_download_subscribed'),
    url(r'download/(?P<organization>%s)/subscribers/churned/?' % ACCT_REGEX,
        ChurnedSubscriptionDownloadView.as_view(),
        name='saas_subscriber_pipeline_download_churned'),
    url(r'^download/(?P<organization>%s)/coupons/' % ACCT_REGEX,
        CouponMetricsDownloadView.as_view(),
        name='saas_metrics_coupons_download'),
    url(r'^download/(?P<organization>%s)/balances/?' % ACCT_REGEX,
        BalancesDownloadView.as_view(), name='saas_balances_download'),
    url(r'^download/(?P<organization>%s)/transfers/?' % ACCT_REGEX,
        TransferDownloadView.as_view(), name='saas_transfers_download'),
]
