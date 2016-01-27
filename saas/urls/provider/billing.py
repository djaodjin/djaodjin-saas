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
URLs related to provider bank account information.
"""

from django.conf.urls import url

from ...settings import ACCT_REGEX
from ...views import ProviderRedirectView
from ...views.billing import (BankAuthorizeView, BankDeAuthorizeView,
    CouponListView, ImportTransactionsView, TransferListView, WithdrawView)


urlpatterns = [
    url(r'^billing/bank/', ProviderRedirectView.as_view(
        pattern_name='saas_update_bank'), name='saas_provider_update_bank'),
    url(r'^billing/coupons/', ProviderRedirectView.as_view(
        pattern_name='saas_coupon_list'), name='saas_provider_coupon_list'),
    url(r'^billing/import/', ProviderRedirectView.as_view(
        pattern_name='saas_provider_import_transactions'),
        name='saas_import_transactions'),
    url(r'^billing/transfers/', ProviderRedirectView.as_view(
        pattern_name='saas_transfer_info'), name='saas_provider_transfer_info'),
    url(r'^billing/withdraw/', ProviderRedirectView.as_view(
        pattern_name='saas_withdraw_funds'),
        name='saas_provider_withdraw_funds'),
    url(r'^billing/(?P<organization>%s)/bank/deauthorize/' % ACCT_REGEX,
        BankDeAuthorizeView.as_view(), name='saas_deauthorize_bank'),
    url(r'^billing/(?P<organization>%s)/bank/' % ACCT_REGEX,
        BankAuthorizeView.as_view(), name='saas_update_bank'),
    url(r'^billing/(?P<organization>%s)/coupons/' % ACCT_REGEX,
        CouponListView.as_view(), name='saas_coupon_list'),
    url(r'^billing/(?P<organization>%s)/import/' % ACCT_REGEX,
        ImportTransactionsView.as_view(), name='saas_import_transactions'),
    url(r'^billing/(?P<organization>%s)/transfers/' % ACCT_REGEX,
        TransferListView.as_view(), name='saas_transfer_info'),
    url(r'^billing/(?P<organization>%s)/withdraw/' % ACCT_REGEX,
        WithdrawView.as_view(), name='saas_withdraw_funds'),
]
