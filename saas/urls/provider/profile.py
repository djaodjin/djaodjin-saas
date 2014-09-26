# Copyright (c) 2014, DjaoDjin inc.
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

from saas.views.profile import (ProviderManagerListView,
    ProviderProfileView, SubscriberListView)
from saas.views.plans import PlanCreateView, PlanUpdateView
from saas.settings import ACCT_REGEX

urlpatterns = patterns('',
    url(r'^subscribers/',
        SubscriberListView.as_view(), name='saas_subscriber_list'),
    url(r'^plans/new/',
        PlanCreateView.as_view(), name='saas_plan_new'),
    url(r'^plans/(?P<plan>%s)/' % ACCT_REGEX,
        PlanUpdateView.as_view(), name='saas_plan_edit'),
    url(r'^managers/',
        ProviderManagerListView.as_view(), name='saas_provider_manager_list'),
    url(r'^$',
        ProviderProfileView.as_view(), name='saas_provider_profile'),
)
