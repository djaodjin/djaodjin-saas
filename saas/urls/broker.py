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
Urls specific to the hosting site (i.e. broker).
"""

from django.conf.urls import url

from .. import settings
from ..views.metrics import BalanceView, RegisteredDownloadView
from ..views.billing import TransactionBaseView
from ..views.download import TransactionDownloadView

urlpatterns = [
    url(r'^download/transactions/?',
        TransactionDownloadView.as_view(),
        name='saas_transactions_download'),
    url(r'^billing/transactions/((?P<selector>%s)/)?' % settings.SELECTOR_RE,
        TransactionBaseView.as_view(), name='saas_broker_transactions'),
    url(r'^metrics/balances/(?P<report>%s)/((?P<year>\d\d\d\d)/)?'
        % settings.ACCT_REGEX,
        BalanceView.as_view(), name='saas_balance'),
    url(r'^download/registered/?',
        RegisteredDownloadView.as_view(),
        name='saas_subscriber_pipeline_download_registered'),
]
