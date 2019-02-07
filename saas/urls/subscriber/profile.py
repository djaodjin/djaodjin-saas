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

'''Urls'''

from django.conf.urls import url

from ...settings import ACCT_REGEX, VERIFICATION_KEY_RE
from ...views.profile import (RoleDetailView, RoleListView,
    OrganizationCreateView, OrganizationProfileView, SubscriptionListView)
from ...views.optins import SubscriptionGrantAcceptView

urlpatterns = [
    url(r'^profile/new/', OrganizationCreateView.as_view(),
        name='saas_organization_create'),
    url(r'^profile/(?P<organization>%s)/roles/(?P<role>%s)/'
        % (ACCT_REGEX, ACCT_REGEX),
        RoleDetailView.as_view(), name='saas_role_detail'),
    url(r'^profile/(?P<organization>%s)/roles/$' % ACCT_REGEX,
        RoleListView.as_view(), name='saas_role_list'),
    url(r'^profile/(?P<organization>%s)/subscriptions/accept/'\
        '(?P<verification_key>%s)/' % (ACCT_REGEX, VERIFICATION_KEY_RE),
        SubscriptionGrantAcceptView.as_view(),
        name='subscription_grant_accept'),
    url(r'^profile/(?P<organization>%s)/subscriptions/' % ACCT_REGEX,
        SubscriptionListView.as_view(), name='saas_subscription_list'),
    url(r'^profile/(?P<organization>%s)/contact/' % ACCT_REGEX,
        OrganizationProfileView.as_view(), name='saas_organization_profile'),
]
