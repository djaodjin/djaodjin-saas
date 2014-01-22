# Copyright (c) 2013, The DjaoDjin Team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

'''Billing urls'''

from django.conf.urls import patterns, include, url

from saas.views.billing import (PlaceOrderView, ChargeReceiptView,
    TransactionListView, redeem_coupon, update_card, pay_now)

urlpatterns = patterns(
    'saas.views.billing',
    url(r'^card', update_card, name='saas_update_card'),
    url(r'^balance/pay/', pay_now, name='saas_pay_now'),
    url(r'^cart/', PlaceOrderView.as_view(), name='saas_organization_cart'),
    url(r'^coupon/redeem/', redeem_coupon, name='saas_redeem_coupon'),
    url(r'^receipt/(?P<charge>[a-zA-Z0-9_]+)',
        ChargeReceiptView.as_view(), name='saas_charge_receipt'),
    url(r'^$', TransactionListView.as_view(), name='saas_billing_info'),
)


