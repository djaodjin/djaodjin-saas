# Copyright (c) 2016, DjaoDjin inc.
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
URLs API for provider resources related to billing
"""

from django.conf.urls import url

from ....settings import ACCT_REGEX
from ....api.backend import RetrieveBankAPIView
from ....api.coupons import CouponListAPIView, CouponDetailAPIView
from ....api.transactions import ReceivablesListAPIView, TransferListAPIView

urlpatterns = [
    url(r'^billing/(?P<organization>%s)/bank/?' % ACCT_REGEX,
        RetrieveBankAPIView.as_view(), name='saas_api_bank'),
    url(r'^billing/(?P<organization>%s)/coupons/(?P<coupon>%s)/?'
        % (ACCT_REGEX, ACCT_REGEX),
        CouponDetailAPIView.as_view(), name='saas_api_coupon_detail'),
    url(r'^billing/(?P<organization>%s)/coupons/?'  % ACCT_REGEX,
        CouponListAPIView.as_view(), name='saas_api_coupon_list'),
    url(r'^billing/(?P<organization>%s)/receivables/?' % ACCT_REGEX,
        ReceivablesListAPIView.as_view(), name='saas_api_receivables'),
    url(r'^billing/(?P<organization>%s)/transfers/?' % ACCT_REGEX,
        TransferListAPIView.as_view(), name='saas_api_transfer_list'),
]
