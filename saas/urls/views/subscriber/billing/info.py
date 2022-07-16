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
URLs responding to GET requests with billing history.
"""

from ..... import settings
from .....compat import path
from .....views.billing import ChargeReceiptView, BillingStatementView
from .....views.download import BillingStatementDownloadView

try:
    from ....views.extra import PrintableChargeReceiptView
    urlpatterns = [
        path('billing/<slug:%s>/receipt/<slug:charge>/printable/' %
            settings.PROFILE_URL_KWARG,
            PrintableChargeReceiptView.as_view(),
            name='saas_printable_charge_receipt'),
        ]
except ImportError:
    urlpatterns = []

urlpatterns += [
    path('billing/<slug:%s>/receipt/<slug:charge>/' %
        settings.PROFILE_URL_KWARG,
        ChargeReceiptView.as_view(), name='saas_charge_receipt'),
    path('billing/<slug:%s>/history/download' %
        settings.PROFILE_URL_KWARG,
        BillingStatementDownloadView.as_view(), name='saas_statement_download'),
    path('billing/<slug:%s>/history/' %
        settings.PROFILE_URL_KWARG,
        BillingStatementView.as_view(), name='saas_billing_info'),
]
