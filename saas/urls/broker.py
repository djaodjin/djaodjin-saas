# Copyright (c) 2018, DjaoDjin inc.
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
Urls specific to the hosting site (i.e. broker).
"""

from django.conf.urls import url

from .. import settings
from ..views.metrics import BalancesView
from ..views.billing import AllTransactions, ChargeListView, VTChargeView
from ..views.download import (BalancesDownloadView, RegisteredDownloadView,
    TransactionDownloadView)

urlpatterns = [
    url(r'^billing/charges/',
        ChargeListView.as_view(), name='saas_charges'),
    url(r'^billing/transactions/((?P<selector>%s)/)?download/?',
        TransactionDownloadView.as_view(),
        name='saas_transactions_download'),
    url(r'^billing/transactions/((?P<selector>%s)/)?' % settings.SELECTOR_RE,
        AllTransactions.as_view(), name='saas_broker_transactions'),
    # Organization refers to the subscriber in the following URL pattern.
    url(r'^billing/(?P<customer>%s)/vtcharge/' % settings.ACCT_REGEX,
        VTChargeView.as_view(), name='saas_organization_vtcharge'),
    url(r'^metrics/balances/(?P<report>%s)/((?P<year>\d\d\d\d)/)?download/?'
        % settings.ACCT_REGEX,
        BalancesDownloadView.as_view(), name='saas_balances_download'),
    url(r'^metrics/balances/(?P<report>%s)/((?P<year>\d\d\d\d)/)?'
        % settings.ACCT_REGEX,
        BalancesView.as_view(), name='saas_balance'),
    url(r'^metrics/registered/download/?',
        RegisteredDownloadView.as_view(),
        name='saas_subscriber_pipeline_download_registered'),
]
