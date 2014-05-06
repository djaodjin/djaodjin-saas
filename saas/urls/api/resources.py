# Copyright (c) 2014, Fortylines LLC
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
URLs for the resources API of djaodjin saas.
"""

from django.conf.urls import patterns, url
from saas.settings import ACCT_REGEX

from saas.api.charges import ChargeResourceView, EmailChargeReceiptAPIView
from saas.api.coupons import CouponListAPIView, CouponDetailAPIView
from saas.api.plans import (PlanActivateAPIView, PlanCreateAPIView,
    PlanResourceView)

urlpatterns = patterns('saas.api',
    url(r'^(?P<organization>%s)/coupons/(?P<coupon>%s)/?'
        % (ACCT_REGEX, ACCT_REGEX),
        CouponDetailAPIView.as_view(), name='saas_api_coupon_detail'),
    url(r'^(?P<organization>%s)/coupons/?' % ACCT_REGEX,
        CouponListAPIView.as_view(), name='saas_api_coupon_list'),
    url(r'^plans/(?P<plan>%s)/activate/' % ACCT_REGEX,
        PlanActivateAPIView.as_view(), name='saas_api_plan_activate'),
    url(r'^plans/(?P<plan>%s)/' % ACCT_REGEX,
        PlanResourceView.as_view(), name='saas_api_plan'),
    url(r'^plans/$',
        PlanCreateAPIView.as_view(), name='saas_api_plan_new'),
    url(r'^charges/(?P<charge>%s)/email/' % ACCT_REGEX,
        EmailChargeReceiptAPIView.as_view(),
        name='saas_api_email_charge_receipt'),
    url(r'^charges/(?P<charge>%s)/' % ACCT_REGEX,
        ChargeResourceView.as_view(), name='saas_api_charge'),
)

