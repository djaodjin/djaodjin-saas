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
URLs responding to GET requests with billing history.
"""

from django.conf.urls import url
from django.views.generic import RedirectView

from ....settings import ACCT_REGEX
from ....views.billing import ChargeReceiptView, BillingStatementView

try:
    from ....views.extra import PrintableChargeReceiptView
    urlpatterns = [
        url(r'^billing/(?P<organization>%s)/'\
'receipt/(?P<charge>[a-zA-Z0-9_]+)/printable/' % ACCT_REGEX,
            PrintableChargeReceiptView.as_view(),
            name='saas_printable_charge_receipt'),
        ]
except ImportError:
    urlpatterns = []

urlpatterns += [
    url(r'^billing/(?P<organization>%s)/receipt/(?P<charge>[a-zA-Z0-9_]+)'
        % ACCT_REGEX,
        ChargeReceiptView.as_view(), name='saas_charge_receipt'),
    url(r'^billing/(?P<organization>%s)/$' % ACCT_REGEX,
        BillingStatementView.as_view(), name='saas_billing_info'),
    url(r'^billing/$',
        RedirectView.as_view(pattern_name='saas_billing_info'),
        name='saas_billing_base'),
]
