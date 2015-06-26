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

"""
URLs related to provider bank account information.
"""

from django.conf.urls import patterns, url

from saas.settings import ACCT_REGEX
from saas.views import ProviderRedirectView
from saas.views.profile import SubscriberListView
from saas.views.plans import PlanCreateView, PlanUpdateView, PlanDeleteView

urlpatterns = patterns('',
    url(r'^profile/contributors/',
        ProviderRedirectView.as_view(pattern_name='saas_contributor_list'),
        name='saas_provider_contributor_list'),
    url(r'^profile/managers/',
        ProviderRedirectView.as_view(pattern_name='saas_manager_list'),
        name='saas_provider_manager_list'),
    url(r'^provider/plans/(?P<plan>%s)/delete/$' % ACCT_REGEX,
        ProviderRedirectView.as_view(pattern_name='saas_plan_delete'),
        name='saas_provider_plan_delete'),
    url(r'^provider/plans/(?P<plan>%s)/$' % ACCT_REGEX,
        ProviderRedirectView.as_view(pattern_name='saas_plan_edit'),
        name='saas_provider_plan_edit'),
    url(r'^provider/plans/',
        ProviderRedirectView.as_view(pattern_name='saas_plan_new'),
        name='saas_provider_plan_new'),
    url(r'^provider/subscribers/',
        ProviderRedirectView.as_view(pattern_name='saas_subscriber_list'),
        name='saas_provider_subscriber_list'),
    url(r'^provider/$',
        ProviderRedirectView.as_view(pattern_name='saas_organization_profile'),
        name='saas_provider_profile'),

    url(r'^provider/(?P<organization>%s)/plans/(?P<plan>%s)/delete/$'
        % (ACCT_REGEX, ACCT_REGEX),
        PlanDeleteView.as_view(), name='saas_plan_delete'),
    url(r'^provider/(?P<organization>%s)/plans/(?P<plan>%s)/?'
        % (ACCT_REGEX, ACCT_REGEX),
        PlanUpdateView.as_view(), name='saas_plan_edit'),
    url(r'^provider/(?P<organization>%s)/plans/' % ACCT_REGEX,
        PlanCreateView.as_view(), name='saas_plan_new'),
    url(r'^provider/(?P<organization>%s)/subscribers/' % ACCT_REGEX,
        SubscriberListView.as_view(), name='saas_subscriber_list'),
)
