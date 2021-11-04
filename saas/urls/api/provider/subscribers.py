# Copyright (c) 2021, DjaoDjin inc.
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

from django.conf.urls import url

from ....api.organizations import SubscribersAPIView, InactiveSubscribersAPIView
from ....api.subscriptions import (ProvidedSubscriptionsAPIView,
    PlanSubscriptionDetailAPIView)
from ....settings import ACCT_REGEX, VERIFICATION_KEY_RE
from ....api.subscriptions import SubscriptionRequestAcceptAPIView


urlpatterns = [
    url(r'^profile/(?P<organization>%s)/subscribers/accept/'\
        '(?P<request_key>%s)/' % (ACCT_REGEX, VERIFICATION_KEY_RE),
        SubscriptionRequestAcceptAPIView.as_view(),
        name='saas_api_subscription_grant_accept'),
    url(r'^profile/(?P<organization>%s)/subscribers/inactive/?' % ACCT_REGEX,
        InactiveSubscribersAPIView.as_view(),
        name='saas_api_inactive_subscribers'),
    url(r'^profile/(?P<organization>%s)/subscribers/?' % ACCT_REGEX,
        SubscribersAPIView.as_view(), name='saas_api_subscribers'),
    url(r'^profile/(?P<organization>%s)/plans/(?P<plan>%s)/subscriptions/'\
    '(?P<subscriber>%s)/'
        % (ACCT_REGEX, ACCT_REGEX, ACCT_REGEX),
        PlanSubscriptionDetailAPIView.as_view(),
        name='saas_api_plan_subscription'),
    url(r'^profile/(?P<organization>%s)/plans/(?P<plan>%s)/subscriptions/'
        % (ACCT_REGEX, ACCT_REGEX),
        ProvidedSubscriptionsAPIView.as_view(),
        name='saas_api_plan_subscriptions'),
]
