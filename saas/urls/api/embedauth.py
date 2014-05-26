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
These URLs embed their own authentication directly into the implementation.

While most URLs rely on external decorators to grant permissions, these
URLs have peculiar requirements more easily encoded as part of the view
implementation itself.
"""

from django.conf.urls import patterns, include, url
from saas.settings import ACCT_REGEX

from saas.api.charges import ChargeRefundAPIView
from saas.api.users import UserListAPIView

urlpatterns = patterns('',
    url(r'^stripe/', include('saas.backends.urls')),
    url(r'^cart/', include('saas.urls.api.cart')),
    url(r'^charges/(?P<charge>%s)/refund/' % ACCT_REGEX,
        ChargeRefundAPIView.as_view(),
        name='saas_api_charge_refund'),
    url(r'^users/?',
        UserListAPIView.as_view(), name='saas_api_user_list'),
)
