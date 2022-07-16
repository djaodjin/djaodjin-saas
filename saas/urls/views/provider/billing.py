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

from .... import settings
from ....compat import path
from ....views.download import TransferDownloadView
from ....views.billing import (ProcessorAuthorizeView, ProcessorDeAuthorizeView,
    CouponListView, ImportTransactionsView, TransferListView, WithdrawView)


urlpatterns = [
    path('billing/<slug:%s>/bank/deauthorize/' %
        settings.PROFILE_URL_KWARG,
        ProcessorDeAuthorizeView.as_view(), name='saas_deauthorize_processor'),
    path('billing/<slug:%s>/bank/' %
        settings.PROFILE_URL_KWARG,
        ProcessorAuthorizeView.as_view(), name='saas_update_bank'),
    path('billing/<slug:%s>/coupons/' %
        settings.PROFILE_URL_KWARG,
        CouponListView.as_view(), name='saas_coupon_list'),
    path('billing/<slug:%s>/transfers/download' %
        settings.PROFILE_URL_KWARG,
        TransferDownloadView.as_view(), name='saas_transfers_download'),
    path('billing/<slug:%s>/transfers/import/' %
        settings.PROFILE_URL_KWARG,
        ImportTransactionsView.as_view(), name='saas_import_transactions'),
    path('billing/<slug:%s>/transfers/withdraw/' %
        settings.PROFILE_URL_KWARG,
        WithdrawView.as_view(), name='saas_withdraw_funds'),
    path('billing/<slug:%s>/transfers/' %
        settings.PROFILE_URL_KWARG,
        TransferListView.as_view(), name='saas_transfer_info'),
]
