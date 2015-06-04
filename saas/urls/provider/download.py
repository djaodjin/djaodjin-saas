# Copyright (c) 2015, DjaoDjin inc.
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

'''Urls to provider downloads'''

from django.conf.urls import patterns, url

from saas.views.metrics import (BalancesDownloadView,
    CouponMetricsDownloadView, SubscriberPipelineSubscribedDownloadView,
    SubscriberPipelineRegisteredDownloadView,
    SubscriberPipelineChurnedDownloadView)
from saas.views.billing import TransferDownloadView

urlpatterns = patterns(
    'saas.views.metrics',
    url(r'^pipeline/registered/?',
        SubscriberPipelineRegisteredDownloadView.as_view(),
        name='saas_subscriber_pipeline_download_registered'),
    url(r'^pipeline/subscribed/?',
        SubscriberPipelineSubscribedDownloadView.as_view(),
        name='saas_subscriber_pipeline_download_subscribed'),
    url(r'^pipeline/churned/?',
        SubscriberPipelineChurnedDownloadView.as_view(),
        name='saas_subscriber_pipeline_download_churned'),
    url(r'^coupons/', CouponMetricsDownloadView.as_view(),
        name='saas_metrics_coupons_download'),
    url(r'^balances/',
        BalancesDownloadView.as_view(), name='saas_balances_download'),
    url(r'^transfers',
        TransferDownloadView.as_view(), name='saas_transfers_download'),
)
