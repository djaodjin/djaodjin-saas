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
URLs related to provider bank account information.
"""

from .... import settings
from ....compat import path, re_path
from ....views.download import (ActiveSubscriptionDownloadView,
    ChurnedSubscriptionDownloadView)
from ....views.optins import SubscriptionRequestAcceptView
from ....views.plans import PlanCreateView, PlanUpdateView, PlanListView
from ....views.profile import SubscriberListView, PlanSubscribersListView


urlpatterns = [
    path('profile/<slug:%s>/plans/<slug:plan>/subscribers/' %
        settings.PROFILE_URL_KWARG,
        PlanSubscribersListView.as_view(), name='saas_plan_subscribers'),
    path('profile/<slug:%s>/plans/new/' %
        settings.PROFILE_URL_KWARG,
        PlanCreateView.as_view(), name='saas_plan_new'),
    path('profile/<slug:%s>/plans/<slug:plan>/' %
        settings.PROFILE_URL_KWARG,
        PlanUpdateView.as_view(), name='saas_plan_edit'),
    path('profile/<slug:%s>/plans/' %
        settings.PROFILE_URL_KWARG,
        PlanListView.as_view(), name='saas_plan_base'),
    path('profile/<slug:%s>/subscribers/active/download' %
        settings.PROFILE_URL_KWARG,
        ActiveSubscriptionDownloadView.as_view(),
        name='saas_subscriber_pipeline_download_subscribed'),
    path('profile/<slug:%s>/subscribers/churned/download' %
        settings.PROFILE_URL_KWARG,
        ChurnedSubscriptionDownloadView.as_view(),
        name='saas_subscriber_pipeline_download_churned'),
    re_path(r'profile/(?P<%s>%s)/subscribers/accept/(?P<request_key>%s)/' % (
        settings.PROFILE_URL_KWARG, settings.SLUG_RE,
        settings.VERIFICATION_KEY_RE),
        SubscriptionRequestAcceptView.as_view(),
        name='subscription_grant_accept'),
    path('profile/<slug:%s>/subscribers/' %
        settings.PROFILE_URL_KWARG,
        SubscriberListView.as_view(), name='saas_subscriber_list'),
]
