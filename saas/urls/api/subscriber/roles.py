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
URLs API for profile managers and custom roles on an Organization
"""

from .... import settings
from ....api.roles import (RoleListAPIView, RoleByDescrListAPIView,
    RoleDetailAPIView)
from ....compat import path, re_path


urlpatterns = [
    re_path(r'profile/(?P<%s>%s)/roles/(?P<role>%s)/(?P<user>%s)' % (
        settings.PROFILE_URL_KWARG, settings.SLUG_RE,
        settings.SLUG_RE, settings.MAYBE_EMAIL_REGEX),
        RoleDetailAPIView.as_view(), name='saas_api_role_detail'),
    path('profile/<slug:%s>/roles/<slug:role>' %
        settings.PROFILE_URL_KWARG,
        RoleByDescrListAPIView.as_view(),
        name='saas_api_roles_by_descr'),
    path('profile/<slug:%s>/roles' %
        settings.PROFILE_URL_KWARG,
        RoleListAPIView.as_view(), name='saas_api_roles'),
]
