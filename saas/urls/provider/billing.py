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
URLs related to provider bank account information.
"""

from ... import settings
from ...compat import re_path
from ...views.download import TransferDownloadView
from ...views.billing import (ProcessorAuthorizeView, ProcessorDeAuthorizeView,
    CouponListView, ImportTransactionsView, TransferListView, WithdrawView)


urlpatterns = [
    re_path(r'^billing/(?P<organization>%s)/bank/deauthorize/' %
        settings.SLUG_RE,
        ProcessorDeAuthorizeView.as_view(), name='saas_deauthorize_processor'),
    re_path(r'^billing/(?P<organization>%s)/bank/' % settings.SLUG_RE,
        ProcessorAuthorizeView.as_view(), name='saas_update_bank'),
    re_path(r'^billing/(?P<organization>%s)/coupons/' % settings.SLUG_RE,
        CouponListView.as_view(), name='saas_coupon_list'),
    re_path(r'^billing/(?P<organization>%s)/transfers/download/?' %
        settings.SLUG_RE,
        TransferDownloadView.as_view(), name='saas_transfers_download'),
    re_path(r'^billing/(?P<organization>%s)/transfers/import/' %
        settings.SLUG_RE,
        ImportTransactionsView.as_view(), name='saas_import_transactions'),
    re_path(r'^billing/(?P<organization>%s)/transfers/withdraw/' %
        settings.SLUG_RE,
        WithdrawView.as_view(), name='saas_withdraw_funds'),
    re_path(r'^billing/(?P<organization>%s)/transfers/' % settings.SLUG_RE,
        TransferListView.as_view(), name='saas_transfer_info'),
]
