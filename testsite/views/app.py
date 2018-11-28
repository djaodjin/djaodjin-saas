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

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.views.generic import TemplateView
from saas.backends import ProcessorConnectionError
from saas.compat import reverse
from saas.models import Organization
from saas.settings import MANAGER


class AppView(TemplateView):

    template_name = 'app.html'

    @property
    def organization(self):
        organization_slug = self.kwargs.get('organization')
        if organization_slug:
            return Organization.objects.get(slug=organization_slug)
        return Organization.objects.accessible_by(
            self.request.user, role_descr=MANAGER).first()

    def get_context_data(self, **kwargs):
        context = super(AppView, self).get_context_data(**kwargs)
        organization = self.organization
        if organization is None:
            messages.error(self.request, "The user '%s' is not manager "\
                "of an attached payment profile (i.e. Organization"
                % self.request.user)
            return context
        try:
            context.update(organization.retrieve_card())
        except ProcessorConnectionError:
            messages.error(self.request, "The payment processor is "\
                "currently unreachable. Sorry for the inconvienience.")
        context.update({'organization': organization})
        urls = {'saas_api_checkout': reverse(
            'saas_api_checkout', args=(organization,)),
                'saas_api_cart': reverse('saas_api_cart'),
                'broker': {'api_charges': reverse('saas_api_charges')}}
        if 'urls' in context:
            for key, val in urls.iteritems():
                if key in context['urls']:
                    context['urls'][key].update(val)
                else:
                    context['urls'].update({key: val})
        else:
            context.update({'urls': urls})
        return context

    def get(self, request, *args, **kwargs):
        if self.organization is None:
            return HttpResponseRedirect(reverse('saas_organization_create'))
        return super(AppView, self).get(request, *args, **kwargs)
