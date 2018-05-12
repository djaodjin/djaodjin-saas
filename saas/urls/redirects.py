# Copyright (c) 2018, DjaoDjin inc.
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

from django.conf.urls import url
from django.views.generic import RedirectView

from ..settings import ACCT_REGEX
from ..views import (OrganizationRedirectView, ProviderRedirectView,
    UserRedirectView)


urlpatterns = [
    url(r'^billing/bank/', ProviderRedirectView.as_view(
        pattern_name='saas_update_bank'), name='saas_provider_update_bank'),
    url(r'^billing/coupons/', ProviderRedirectView.as_view(
        pattern_name='saas_coupon_list'), name='saas_provider_coupon_list'),
    url(r'^billing/import/', ProviderRedirectView.as_view(
        pattern_name='saas_provider_import_transactions'),
        name='saas_import_transactions'),
    url(r'^billing/transfers/download/?',
        ProviderRedirectView.as_view(pattern_name='saas_transfers_download'),
        name='saas_provider_transfers_download'),
    url(r'^billing/transfers/', ProviderRedirectView.as_view(
        pattern_name='saas_transfer_info'), name='saas_provider_transfer_info'),
    url(r'^billing/withdraw/', ProviderRedirectView.as_view(
        pattern_name='saas_withdraw_funds'),
        name='saas_provider_withdraw_funds'),
    url(r'^billing/cart/',
        OrganizationRedirectView.as_view(pattern_name='saas_organization_cart'),
        name='saas_cart'),
    url(r'^profile/roles/(?P<role>%s)/' % ACCT_REGEX,
        ProviderRedirectView.as_view(pattern_name='saas_role_detail'),
        name='saas_provider_role_list'),
    url(r'^profile/plans/new/',
        ProviderRedirectView.as_view(pattern_name='saas_plan_new'),
        name='saas_provider_plan_new'),
    url(r'^profile/plans/(?P<plan>%s)/' % ACCT_REGEX,
        ProviderRedirectView.as_view(pattern_name='saas_plan_edit'),
        name='saas_provider_plan_edit'),
    url(r'^profile/plans/',
        ProviderRedirectView.as_view(pattern_name='saas_plan_base'),
        name='saas_provider_plan_base'),
    url(r'^profile/subscribers/active/download/?',
        ProviderRedirectView.as_view(
            pattern_name='saas_subscriber_pipeline_download_subscribed'),
        name='saas_provider_subscriber_pipeline_download_subscribed'),
    url(r'^profile/subscribers/churned/download/?',
        ProviderRedirectView.as_view(
            pattern_name='saas_subscriber_pipeline_download_churned'),
        name='saas_provider_subscriber_pipeline_download_churned'),
    url(r'^profile/subscribers/',
        ProviderRedirectView.as_view(pattern_name='saas_subscriber_list'),
        name='saas_provider_subscriber_list'),
    url(r'^metrics/dashboard/',
        ProviderRedirectView.as_view(pattern_name='saas_dashboard'),
        name='saas_provider_dashboard'),
    url(r'^metrics/revenue/',
        ProviderRedirectView.as_view(pattern_name='saas_metrics_summary'),
        name='saas_provider_metrics_revenue'),
    url(r'^metrics/plans/',
        ProviderRedirectView.as_view(pattern_name='saas_metrics_plans'),
        name='saas_provider_metrics_plans'),
    url(r'^metrics/coupons/download/?',
        ProviderRedirectView.as_view(
            pattern_name='saas_metrics_coupons_download'),
        name='saas_provider_metrics_coupons_download'),
    url(r'^metrics/coupons/((?P<coupon>%s)/)?' % ACCT_REGEX,
        ProviderRedirectView.as_view(pattern_name='saas_metrics_coupons'),
        name='saas_provider_metrics_coupons'),

    url(r'^billing/(?P<organization>%s)/$' % ACCT_REGEX,
        RedirectView.as_view(permanent=False, pattern_name='saas_billing_info'),
        name='saas_billing_redirect'),
    url(r'^billing/$',
        OrganizationRedirectView.as_view(pattern_name='saas_billing_info'),
        name='saas_billing_base'),
    url(r'^profile/(?P<organization>%s)/$' % ACCT_REGEX,
        RedirectView.as_view(permanent=False,
            pattern_name='saas_organization_profile'),
        name='saas_profile_redirect'),
    url(r'^profile/$', OrganizationRedirectView.as_view(
            pattern_name='saas_organization_profile'),
        name='saas_profile'),
    url(r'^provider/$',
        ProviderRedirectView.as_view(pattern_name='saas_organization_profile'),
        name='saas_provider_profile'),
    url(r'^metrics/$',
        ProviderRedirectView.as_view(pattern_name='saas_metrics_summary'),
        name='saas_provider_metrics_summary'),
    url(r'^users/roles/$',
        UserRedirectView.as_view(pattern_name='saas_user_product_list'),
        name='saas_accessibles'),
]
