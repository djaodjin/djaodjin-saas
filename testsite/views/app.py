# Copyright (c) 2025, DjaoDjin inc.
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

from django.views.generic import TemplateView
from saas import settings as saas_settings
from saas.compat import reverse
from saas.helpers import update_context_urls
from saas.utils import get_organization_model


class AppView(TemplateView):

    template_name = 'app.html'
    organization_model = get_organization_model()
    organization_url_kwarg = saas_settings.PROFILE_URL_KWARG

    @property
    def organization(self):
        organization_slug = self.kwargs.get(self.organization_url_kwarg)
        if organization_slug:
            return self.organization_model.objects.get(slug=organization_slug)
        return self.organization_model.objects.accessible_by(
            self.request.user, role_descr=saas_settings.MANAGER).first()

    def get_context_data(self, **kwargs):
        context = super(AppView, self).get_context_data(**kwargs)
        organization = self.organization
        if organization is None:
            return context

        context.update({'organization': organization})
        update_context_urls(context, {
            'saas_api_checkout': reverse(
            'saas_api_checkout', args=(organization,)),
                'saas_api_cart': reverse('saas_api_cart'),
                'broker': {'api_charges': reverse('saas_api_charges')}
        })
        return context
