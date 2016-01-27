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
URLs updating processing information and inserting transactions
through POST requests.
"""

from django.conf.urls import url

from ....settings import ACCT_REGEX
from ....views.billing import (CartPeriodsView, CartSeatsView,
    CardUpdateView, CartView, BalanceView)


urlpatterns = [
    url(r'^billing/(?P<organization>%s)/cart-seats/' % ACCT_REGEX,
        CartSeatsView.as_view(), name='saas_cart_seats'),
    url(r'^billing/(?P<organization>%s)/cart-periods/' % ACCT_REGEX,
        CartPeriodsView.as_view(), name='saas_cart_periods'),
    url(r'^billing/(?P<organization>%s)/cart/' % ACCT_REGEX,
        CartView.as_view(), name='saas_organization_cart'),
    url(r'^billing/(?P<organization>%s)/card/' % ACCT_REGEX,
        CardUpdateView.as_view(), name='saas_update_card'),
    # Implementation Note: <subscribed_plan> (not <plan>) such that
    # the required_manager decorator does not raise a PermissionDenied
    # for a plan <organization> is subscribed to.
    url(r'^billing/(?P<organization>%s)/balance/((?P<subscribed_plan>%s)/)?'
        % (ACCT_REGEX, ACCT_REGEX),
        BalanceView.as_view(), name='saas_organization_balance'),
]
