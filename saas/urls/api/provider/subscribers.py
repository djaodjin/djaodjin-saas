# Copyright (c) 2024, DjaoDjin inc.
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
API URLs for a provider subcribers.
"""

from .... import settings
from ....api.organizations import (ActiveSubscribersAPIView,
    EngagedSubscribersAPIView, ProviderAccessiblesAPIView,
    UnengagedSubscribersAPIView)
from ....api.subscriptions import (ActiveSubscriberSubscriptionsAPIView,
    AllSubscriberSubscriptionsAPIView, ChurnedSubscribersAPIView,
    PlanAllSubscribersAPIView,
    PlanActiveSubscribersAPIView, PlanChurnedSubscribersAPIView,
    PlanSubscriptionDetailAPIView, SubscriptionRequestAcceptAPIView)
from ....compat import path, re_path


urlpatterns = [
    re_path(r'profile/(?P<%s>%s)/subscribers/accept/(?P<request_key>%s)' % (
        settings.PROFILE_URL_KWARG, settings.SLUG_RE,
        settings.VERIFICATION_KEY_RE),
        SubscriptionRequestAcceptAPIView.as_view(),
        name='saas_api_subscription_grant_accept'),
    path('profile/<slug:%s>/subscribers/subscriptions/all' %
        settings.PROFILE_URL_KWARG,
        AllSubscriberSubscriptionsAPIView.as_view(),
        name='saas_api_subscribed_and_churned'),
    path('profile/<slug:%s>/subscribers/subscriptions/churned' %
        settings.PROFILE_URL_KWARG,
        ChurnedSubscribersAPIView.as_view(),
        name='saas_api_churned'),
    path('profile/<slug:%s>/subscribers/subscriptions' %
        settings.PROFILE_URL_KWARG,
        ActiveSubscriberSubscriptionsAPIView.as_view(),
        name='saas_api_subscribed'),

    path('profile/<slug:%s>/subscribers/engaged' %
        settings.PROFILE_URL_KWARG,
        EngagedSubscribersAPIView.as_view(),
        name='saas_api_engaged_subscribers'),
    path('profile/<slug:%s>/subscribers/unengaged' %
        settings.PROFILE_URL_KWARG,
        UnengagedSubscribersAPIView.as_view(),
        name='saas_api_unengaged_subscribers'),
    path('profile/<slug:%s>/subscribers/all' %
        settings.PROFILE_URL_KWARG,
        ProviderAccessiblesAPIView.as_view(), name='saas_api_subscribers_all'),
    path('profile/<slug:%s>/subscribers' %
        settings.PROFILE_URL_KWARG,
        ActiveSubscribersAPIView.as_view(), name='saas_api_subscribers'),

    path('profile/<slug:%s>/plans/<slug:plan>/subscriptions/all' %
        settings.PROFILE_URL_KWARG,
        PlanAllSubscribersAPIView.as_view(),
        name='saas_api_plan_subscribers_all'),
    path('profile/<slug:%s>/plans/<slug:plan>/subscriptions/churned' %
        settings.PROFILE_URL_KWARG,
        PlanChurnedSubscribersAPIView.as_view(),
        name='saas_api_plan_subscribers_churned'),
    path(
    'profile/<slug:%s>/plans/<slug:plan>/subscriptions/<slug:subscriber>' %
        settings.PROFILE_URL_KWARG,
        PlanSubscriptionDetailAPIView.as_view(),
        name='saas_api_plan_subscription'),
    path('profile/<slug:%s>/plans/<slug:plan>/subscriptions' %
        settings.PROFILE_URL_KWARG,
        PlanActiveSubscribersAPIView.as_view(),
        name='saas_api_plan_subscribers'),
]
