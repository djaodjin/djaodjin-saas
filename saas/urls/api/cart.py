# Copyright (c) 2024, DjaoDjin inc.
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
URLs for the cart API of djaodjin saas.
"""

from ...api.agreements import AgreementDetailAPIView, AgreementListAPIView
from ...api.billing import (CartItemAPIView, CartItemUploadAPIView,
                            CouponRedeemAPIView)
from ...api.plans import PricingAPIView
from ...compat import path

urlpatterns = [
    path('pricing',
        PricingAPIView.as_view(), name='saas_api_pricing'),
    path('cart/redeem',
        CouponRedeemAPIView.as_view(), name='saas_api_redeem_coupon'),
    path('cart/<slug:plan>/upload',
        CartItemUploadAPIView.as_view(), name='saas_api_cart_upload'),
    path('cart', CartItemAPIView.as_view(), name='saas_api_cart'),
    path('legal/<slug:agreement>', AgreementDetailAPIView.as_view(),
        name='saas_api_legal_detail'),
    path('legal', AgreementListAPIView.as_view(), name='saas_api_legal'),
]
