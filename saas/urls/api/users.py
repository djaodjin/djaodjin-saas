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
URLs for API related to users accessible by.
"""

from ... import settings
from ...api.roles import (AccessibleByListAPIView, AccessibleDetailAPIView,
    RoleAcceptAPIView, AccessibleByDescrListAPIView, UserProfileListAPIView)
from ...compat import re_path

urlpatterns = [
    re_path(
        r'^users/(?P<user>%s)/accessibles/accept/(?P<verification_key>%s)' % (
        settings.MAYBE_EMAIL_REGEX, settings.VERIFICATION_KEY_RE),
        RoleAcceptAPIView.as_view(), name='saas_api_accessibles_accept'),
    re_path(
        r'^users/(?P<user>%s)/accessibles/(?P<role>%s)/(?P<organization>%s)'
        % (settings.SLUG_RE, settings.SLUG_RE, settings.SLUG_RE),
        AccessibleDetailAPIView.as_view(), name='saas_api_accessible_detail'),
    re_path(r'^users/(?P<user>%s)/accessibles/(?P<role>%s)' % (
        settings.SLUG_RE, settings.SLUG_RE),
        AccessibleByDescrListAPIView.as_view(),
        name='saas_api_accessibles_by_descr'),
    re_path(r'^users/(?P<user>%s)/accessibles' % settings.MAYBE_EMAIL_REGEX,
        AccessibleByListAPIView.as_view(), name='saas_api_accessibles'),
    re_path(r'^users/(?P<user>%s)/profiles' % settings.MAYBE_EMAIL_REGEX,
        UserProfileListAPIView.as_view(), name='saas_api_user_profiles'),
]
