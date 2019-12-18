# Copyright (c) 2019, DjaoDjin inc.
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
URLs API for resources
"""

from django.conf.urls import url

from .... import settings
from ....api.billing import CheckoutAPIView
from ....api.backend import PaymentMethodDetailAPIView
from ....api.transactions import BillingsAPIView, StatementBalanceAPIView


urlpatterns = [
    url(r'^billing/(?P<organization>%s)/balance/?' % settings.ACCT_REGEX,
        StatementBalanceAPIView.as_view(),
        name='saas_api_cancel_balance_due'),
    url(r'^billing/(?P<organization>%s)/history/?' % settings.ACCT_REGEX,
        BillingsAPIView.as_view(), name='saas_api_billings'),
    url(r'^billing/(?P<organization>%s)/card/?' % settings.ACCT_REGEX,
        PaymentMethodDetailAPIView.as_view(), name='saas_api_card'),
    url(r'^billing/(?P<organization>%s)/checkout/?' % settings.ACCT_REGEX,
        CheckoutAPIView.as_view(), name='saas_api_checkout'),
]
