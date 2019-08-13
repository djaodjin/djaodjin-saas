# Copyright (c) 2019, DjaoDjin inc.
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
URLs API for profile managers and custom roles on an Organization
"""

from django.conf.urls import url

from ....api.roles import (RoleListAPIView, RoleByDescrListAPIView,
    RoleDetailAPIView)
from ....settings import ACCT_REGEX, MAYBE_EMAIL_REGEX


urlpatterns = [
    url(r'^profile/(?P<organization>%s)/roles/(?P<role>%s)/(?P<user>%s)/?'
        % (ACCT_REGEX, ACCT_REGEX, MAYBE_EMAIL_REGEX),
        RoleDetailAPIView.as_view(), name='saas_api_role_detail'),
    url(r'^profile/(?P<organization>%s)/roles/(?P<role>%s)/?'
        % (ACCT_REGEX, ACCT_REGEX),
        RoleByDescrListAPIView.as_view(),
        name='saas_api_roles_by_descr'),
    url(r'^profile/(?P<organization>%s)/roles/?' % ACCT_REGEX,
        RoleListAPIView.as_view(), name='saas_api_roles'),
]
