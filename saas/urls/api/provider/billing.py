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
URLs API for provider resources related to billing
"""

from .... import settings
from ....api.backend import RetrieveBankAPIView
from ....api.coupons import CouponListCreateAPIView, CouponDetailAPIView
from ....api.transactions import (ReceivablesListAPIView,
    TransferListAPIView, ImportTransactionsAPIView)
from ....compat import re_path

urlpatterns = [
    re_path(r'^billing/(?P<organization>%s)/bank/?' % settings.SLUG_RE,
        RetrieveBankAPIView.as_view(), name='saas_api_bank'),
    re_path(r'^billing/(?P<organization>%s)/coupons/(?P<coupon>%s)/?'
        % (settings.SLUG_RE, settings.SLUG_RE),
        CouponDetailAPIView.as_view(), name='saas_api_coupon_detail'),
    re_path(r'^billing/(?P<organization>%s)/coupons/?'  % settings.SLUG_RE,
        CouponListCreateAPIView.as_view(), name='saas_api_coupon_list'),
    re_path(r'^billing/(?P<organization>%s)/receivables/?' % settings.SLUG_RE,
        ReceivablesListAPIView.as_view(), name='saas_api_receivables'),
    re_path(r'^billing/(?P<organization>%s)/transfers/import/' %
        settings.SLUG_RE, ImportTransactionsAPIView.as_view(),
        name='saas_api_import_transactions'),
    re_path(r'^billing/(?P<organization>%s)/transfers/?' % settings.SLUG_RE,
        TransferListAPIView.as_view(), name='saas_api_transfer_list'),
]
