# Copyright (c) 2018, DjaoDjin inc.
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
API URLs for profile resources typically associated to a provider
(i.e. ``Plan``).
"""

from django.conf.urls import url

from ....api.plans import (PlanListCreateAPIView, PlanDetailAPIView)
from ....api.roles import (RoleDescriptionListCreateView,
    RoleDescriptionDetailView)
from ....api.organizations import SubscribersAPIView
from ....api.subscriptions import (PlanSubscriptionsAPIView,
    PlanSubscriptionDetailAPIView)
from ....settings import ACCT_REGEX, VERIFICATION_KEY_RE
from ....api.subscriptions import SubscriptionRequestAcceptAPIView

urlpatterns = [
    url(r'^profile/(?P<organization>%s)/roles/describe/(?P<role>%s)/?'
        % (ACCT_REGEX, ACCT_REGEX),
        RoleDescriptionDetailView.as_view(),
        name='saas_api_role_description_detail'),
    url(r'^profile/(?P<organization>%s)/roles/describe/?' % ACCT_REGEX,
        RoleDescriptionListCreateView.as_view(),
        name='saas_api_role_description_list'),
    url(r'^profile/(?P<organization>%s)/plans/(?P<plan>%s)/subscriptions/'\
    '(?P<subscriber>%s)/'
        % (ACCT_REGEX, ACCT_REGEX, ACCT_REGEX),
        PlanSubscriptionDetailAPIView.as_view(),
        name='saas_api_plan_subscription'),
    url(r'^profile/(?P<organization>%s)/plans/(?P<plan>%s)/subscriptions/'
        % (ACCT_REGEX, ACCT_REGEX),
        PlanSubscriptionsAPIView.as_view(), name='saas_api_plan_subscriptions'),
    url(r'^profile/(?P<organization>%s)/plans/(?P<plan>%s)/?'
        % (ACCT_REGEX, ACCT_REGEX),
        PlanDetailAPIView.as_view(), name='saas_api_plan'),
    url(r'^profile/(?P<organization>%s)/plans/?' % ACCT_REGEX,
        PlanListCreateAPIView.as_view(), name='saas_api_plans'),
    url(r'^profile/(?P<organization>%s)/subscribers/accept/'\
        '(?P<request_key>%s)/' % (ACCT_REGEX, VERIFICATION_KEY_RE),
        SubscriptionRequestAcceptAPIView.as_view(),
        name='saas_api_subscription_grant_accept'),
    url(r'^profile/(?P<organization>%s)/subscribers/?' % ACCT_REGEX,
        SubscribersAPIView.as_view(), name='saas_api_subscribers'),
]
