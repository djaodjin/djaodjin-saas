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

import debug_toolbar
from django.conf import settings
from django.conf.urls.static import static
from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.views.i18n import JavaScriptCatalog
from saas.compat import reverse_lazy
from saas.views import OrganizationRedirectView, UserRedirectView
from saas.views.plans import CartPlanListView
from urldecorators import include, url

from testsite.views.app import AppView
from testsite.views.organization import OrganizationListView, UserProfileView
from testsite.views.registration import PersonalRegistrationView

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

from . import signals


def url_prefixed(regex, view, name=None, decorators=None):
    """
    Returns a urlpattern for public pages.
    """
    return url(r'^' + regex, view, name=name, decorators=decorators)


# admin doc and panel
try:
    urlpatterns = [
        url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
        url(r'^admin/', admin.site.urls),
    ]
except ImproperlyConfigured: # Django <= 1.9
    urlpatterns = [
        url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
        url(r'^admin/', include(admin.site.urls)),
    ]

urlpatterns += \
    static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + [
    url(r'^__debug__/', include(debug_toolbar.urls)),
    url(r'^jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
    url_prefixed(r'register/$',
        PersonalRegistrationView.as_view(
            success_url=reverse_lazy('home')),
        name='registration_register'),
    url_prefixed(r'', include('saas.urls.users'),
        decorators=['django.contrib.auth.decorators.login_required']),
    url_prefixed(r'users/(?P<user>[\w.@+-]+)/',
        UserProfileView.as_view(), name='users_profile',
        decorators=['django.contrib.auth.decorators.login_required']),
    url_prefixed(r'users/',
        UserRedirectView.as_view(), name='accounts_profile',
        decorators=['django.contrib.auth.decorators.login_required']),
    url_prefixed(r'', include('django.contrib.auth.urls')),
    url_prefixed(r'saas/$',
        OrganizationListView.as_view(), name='saas_organization_list',
        decorators=['django.contrib.auth.decorators.login_required']),
    url_prefixed(r'$', TemplateView.as_view(template_name='index.html'),
        name='home'),
    url_prefixed(r'billing/cart/',
        login_required(
            OrganizationRedirectView.as_view(
                implicit_create_on_none=True,
                pattern_name='saas_organization_cart'),
            login_url=reverse_lazy('registration_register')),
        name='saas_cart'),
    # saas urls with provider key to implement marketplace.
    url_prefixed(r'api/', include('saas.backends.urls.api')),
    url_prefixed(r'api/', include('saas.urls.api.cart')),
    url_prefixed(r'api/', include('saas.urls.api.users'),
        decorators=['saas.decorators.requires_self_provider']),
    url_prefixed(r'api/', include('saas.urls.api.broker'),
        decorators=['saas.decorators.requires_provider_only']),
    url_prefixed(r'api/', include('saas.urls.api.search'),
        decorators=['django.contrib.auth.decorators.login_required']),
    # api/charges/:charge/refund must be before api/charges/
    url_prefixed(r'api/',
        include('saas.urls.api.provider.charges'),
        decorators=['saas.decorators.requires_provider_only']),
    url_prefixed(r'api/',
        include('saas.urls.api.provider.billing'),
        decorators=['saas.decorators.requires_direct']),
    url_prefixed(r'api/',
        include('saas.urls.api.provider.roles'),
        decorators=['saas.decorators.requires_direct']),
    url_prefixed(r'api/',
        include('saas.urls.api.provider.subscribers'),
        decorators=['saas.decorators.requires_direct']),
    url_prefixed(r'api/',
        include('saas.urls.api.provider.plans'),
        decorators=['saas.decorators.requires_direct']),
    url_prefixed(r'api/',
        include('saas.urls.api.provider.metrics'),
        decorators=['saas.decorators.requires_direct']),
    url_prefixed(r'api/', include('saas.urls.api.subscriber'),
        decorators=['saas.decorators.requires_provider']),
    url_prefixed(r'pricing/', CartPlanListView.as_view(),
        name='saas_cart_plan_list'),
    url_prefixed(r'', include('saas.urls.request'),
        decorators=['django.contrib.auth.decorators.login_required']),
    url_prefixed(r'', include('saas.urls.noauth')),
    url_prefixed(r'', include('saas.urls.broker'),
        decorators=['saas.decorators.requires_direct']),
    url_prefixed(r'', include('saas.urls.redirects'),
        decorators=['django.contrib.auth.decorators.login_required']),
    url_prefixed(r'', include('saas.urls.provider'),
        decorators=['saas.decorators.requires_direct']),
    url_prefixed(r'', include('saas.urls.subscriber'),
        decorators=['saas.decorators.requires_provider',
                    'saas.decorators.requires_agreement']),
    url_prefixed(r'', include('saas.backends.urls.views')),
    url_prefixed(r'app/((?P<organization>[a-zA-Z0-9_-]+)/)?',
        AppView.as_view(template_name='app.html'), name='app',
        decorators=['django.contrib.auth.decorators.login_required']),
]
