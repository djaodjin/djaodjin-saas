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
URLs API for resources available typically only to the broker platform.
"""

from ... import settings
from ...api.balances import (BalanceLineListAPIView, BrokerBalancesAPIView,
    BalanceLineDetailAPIView)
from ...api.charges import ChargeListAPIView
from ...api.organizations import OrganizationListAPIView
from ...api.transactions import TransactionListAPIView
from ...api.users import RegisteredAPIView
from ...compat import path, re_path


urlpatterns = [
    path('billing/transactions',
        TransactionListAPIView.as_view(), name='saas_api_transactions'),
    path('billing/charges', ChargeListAPIView.as_view(),
        name='saas_api_charges'),
    re_path(r'^metrics/balances/(?P<report>%s)/lines/(?P<rank>\d+)' % (
        settings.SLUG_RE), BalanceLineDetailAPIView.as_view(),
        name='saas_api_balance_line'),
    path('metrics/balances/<slug:report>/lines',
        BalanceLineListAPIView.as_view(), name='saas_api_balance_lines'),
    path('metrics/balances/<slug:report>',
        BrokerBalancesAPIView.as_view(), name='saas_api_broker_balances'),
    path('metrics/registered',
        RegisteredAPIView.as_view(), name='saas_api_registered'),
]
