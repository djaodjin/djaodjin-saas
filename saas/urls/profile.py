# Copyright (c) 2014, Fortylines LLC
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

'''Urls'''

from django.conf.urls import patterns, include, url

from saas.views.profile import (
    ContributorListView, ManagerListView, SubscriberListView)

urlpatterns = patterns(
    'saas.views.profile',
    url(r'^contributors/add',
        'organization_add_contributors', name='saas_add_contributors'),
    url(r'^contributors/remove',
        'organization_remove_contributors', name='saas_remove_contributors'),
    url(r'^contributors/',
        ContributorListView.as_view(), name='saas_contributor_list'),
    url(r'^managers/add',
        'organization_add_managers', name='saas_add_managers'),
    url(r'^managers/remove',
        'organization_remove_managers', name='saas_remove_managers'),
    url(r'^managers/',
        ManagerListView.as_view(), name='saas_manager_list'),
    url(r'^subscribers/',
        SubscriberListView.as_view(), name='saas_subscriber_list'),
    url(r'^$',
        'organization_profile', name='saas_organization_profile'),
)

