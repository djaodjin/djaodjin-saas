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

from urldecorators import patterns, include, url
from django.views.generic import TemplateView

from saas.views.profile import OrganizationListView

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # admin doc and panel
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),

    url(r'^accounts/', include('django.contrib.auth.urls')),
    url(r'^saas/$',
        OrganizationListView.as_view(), name='saas_organization_list',
        decorators = ['django.contrib.auth.decorators.login_required']),
    url(r'^saas/metrics/general/', 'saas.views.metrics.organization_overall',
        name='saas_metrics_overall'),
    url(r'^saas/metrics/stats/', 'saas.views.metrics.statistic',
        name='saas_metrics_stats'),
    url(r'^legal/', include('saas.urls.legal')),
    url(r'^processor/', include('saas.backends.urls')),
    url(r'^saas/', include('saas.urls'),
        decorators = ['saas.decorators.requires_manager']),
    url(r'^$',TemplateView.as_view(template_name='index.html'), name='home'),
)
