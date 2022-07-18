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
Redirects that need to appear before `urls.views.provider` and
`urls.views.subscriber`
"""

from ...compat import path
from ...views import (OrganizationRedirectView, ProviderRedirectView,
    UserRedirectView)
from ...views.profile import OrganizationCreateView


urlpatterns = [
    path('billing/bank/', ProviderRedirectView.as_view(
        pattern_name='saas_update_bank'), name='saas_provider_update_bank'),
    path('billing/coupons/', ProviderRedirectView.as_view(
        pattern_name='saas_coupon_list'), name='saas_provider_coupon_list'),
    path('billing/import/', ProviderRedirectView.as_view(
        pattern_name='saas_provider_import_transactions'),
        name='saas_import_transactions'),
    path('billing/transfers/', ProviderRedirectView.as_view(
        pattern_name='saas_transfer_info'), name='saas_provider_transfer_info'),
    path('billing/withdraw/', ProviderRedirectView.as_view(
        pattern_name='saas_withdraw_funds'),
        name='saas_provider_withdraw_funds'),
    path('billing/cart/',
        OrganizationRedirectView.as_view(pattern_name='saas_organization_cart'),
        name='saas_cart'),

    path('profile/new/', OrganizationCreateView.as_view(),
        name='saas_organization_create'),
    path('profile/roles/<slug:role>/',
        ProviderRedirectView.as_view(pattern_name='saas_role_detail'),
        name='saas_provider_role_list'),
    path('profile/plans/new/',
        ProviderRedirectView.as_view(pattern_name='saas_plan_new'),
        name='saas_provider_plan_new'),
    path('profile/plans/<slug:plan>/',
        ProviderRedirectView.as_view(pattern_name='saas_plan_edit'),
        name='saas_provider_plan_edit'),
    path('profile/plans/',
        ProviderRedirectView.as_view(pattern_name='saas_plan_base'),
        name='saas_provider_plan_base'),
    path('profile/subscribers/',
        ProviderRedirectView.as_view(pattern_name='saas_subscriber_list'),
        name='saas_provider_subscriber_list'),

    path('metrics/dashboard/',
        ProviderRedirectView.as_view(pattern_name='saas_dashboard'),
        name='saas_provider_dashboard'),
    path('metrics/revenue/',
        ProviderRedirectView.as_view(pattern_name='saas_metrics_summary'),
        name='saas_provider_metrics_revenue'),
    path('metrics/plans/',
        ProviderRedirectView.as_view(pattern_name='saas_metrics_plans'),
        name='saas_provider_metrics_plans'),
    path('metrics/coupons/<slug:coupon>/',
        ProviderRedirectView.as_view(pattern_name='saas_metrics_coupons'),
        name='saas_provider_metrics_coupon'),
    path('metrics/coupons/',
        ProviderRedirectView.as_view(pattern_name='saas_metrics_coupons'),
        name='saas_provider_metrics_coupon_list'),

    path('users/roles/',
        UserRedirectView.as_view(pattern_name='saas_user_product_list'),
        name='saas_accessibles'),
]
