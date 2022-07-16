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
URLs updating processing information and inserting transactions
through POST requests.
"""

from ..... import settings
from .....compat import path
from .....views.billing import (CartPeriodsView, CartSeatsView,
    CardUpdateView, CartView, BalanceView, CheckoutView)


urlpatterns = [
    path('billing/<slug:%s>/checkout/' %
        settings.PROFILE_URL_KWARG,
        CheckoutView.as_view(), name='saas_checkout'),
    path('billing/<slug:%s>/cart-seats/' %
        settings.PROFILE_URL_KWARG,
        CartSeatsView.as_view(), name='saas_cart_seats'),
    path('billing/<slug:%s>/cart-periods/' %
        settings.PROFILE_URL_KWARG,
        CartPeriodsView.as_view(), name='saas_cart_periods'),
    path('billing/<slug:%s>/cart/' %
        settings.PROFILE_URL_KWARG,
        CartView.as_view(), name='saas_organization_cart'),
    path('billing/<slug:%s>/card/' %
        settings.PROFILE_URL_KWARG,
        CardUpdateView.as_view(), name='saas_update_card'),
    # Implementation Note: <subscribed_plan> (not <plan>) such that
    # the required_manager decorator does not raise a PermissionDenied
    # for a plan <organization> is subscribed to.
    path('billing/<slug:%s>/balance/<slug:subscribed_plan>/' %
        settings.PROFILE_URL_KWARG,
        BalanceView.as_view(), name='saas_subscription_balance'),
    path('billing/<slug:%s>/balance/' %
        settings.PROFILE_URL_KWARG,
        BalanceView.as_view(), name='saas_organization_balance'),
]
