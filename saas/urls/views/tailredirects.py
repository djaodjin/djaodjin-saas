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
Redirects that need to appear after `urls.views.provider` and
`urls.views.subscriber`
"""

from django.views.generic import RedirectView

from ... import settings
from ...compat import path
from ...views import OrganizationRedirectView, ProviderRedirectView

urlpatterns = [
    path(r'billing/<slug:%s>/' %
        settings.PROFILE_URL_KWARG,
        RedirectView.as_view(permanent=False, pattern_name='saas_billing_info'),
        name='saas_billing_redirect'),
    path('billing/',
        OrganizationRedirectView.as_view(pattern_name='saas_billing_info'),
        name='saas_billing_base'),

    path(r'profile/<slug:%s>/' %
        settings.PROFILE_URL_KWARG,
        RedirectView.as_view(permanent=False,
            pattern_name='saas_organization_profile'),
        name='saas_profile_redirect'),
    path('profile/', OrganizationRedirectView.as_view(
            pattern_name='saas_organization_profile'),
        name='saas_profile'),

    path('metrics/',
        ProviderRedirectView.as_view(pattern_name='saas_metrics_summary'),
        name='saas_provider_metrics_summary'),

    path('provider/',
        ProviderRedirectView.as_view(pattern_name='saas_organization_profile'),
        name='saas_provider_profile'),
]
