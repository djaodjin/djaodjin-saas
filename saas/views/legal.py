# Copyright (c) 2014, DjaoDjin inc.
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

'''Dynamic pages dealing with legal agreements.'''

import urlparse

from django import forms
from django.conf import settings
from django.contrib.sites.models import Site
from django.template import loader
from django.template.base import Context
from django.forms.widgets import CheckboxInput
from django.core.context_processors import csrf
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView

from saas.models import Organization, Agreement, Signature

class AgreementDetailView(DetailView):

    model = Agreement

    def get_context_data(self, **kwargs):
        context = super(AgreementDetailView, self).get_context_data(**kwargs)
        context.update({
                'page': _read_agreement_file(context['agreement'].slug)})
        return context


class AgreementListView(ListView):

    model = Agreement

    def get_context_data(self, **kwargs):
        context = super(AgreementListView, self).get_context_data(**kwargs)
        context['organization'] = Organization.objects.get_site_owner()
        return context


class SignatureForm(forms.Form):
    '''Base form to sign legal agreements.'''

    read_terms = forms.fields.BooleanField(
        label='I have read and understand these terms and conditions',
        widget=CheckboxInput)

    def __init__(self, data=None):
        forms.Form.__init__(self, data=data, label_suffix='')


def _read_agreement_file(slug, context=None):
    import markdown
    if not context:
        context = {
            'site': Site.objects.get(pk=settings.SITE_ID),
            'organization': Organization.objects.get_site_owner()}
    source, _ = loader.find_template('saas/agreements/legal_%s.md' % slug)
    return markdown.markdown(source.render(Context(context)))

@login_required
def sign_agreement(request, slug,
                   redirect_field_name=REDIRECT_FIELD_NAME):
    '''Request signature of a legal agreement.'''
    context = {'user': request.user}
    context.update(csrf(request))
    if request.method == 'POST':
        form = SignatureForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['read_terms']:
                Signature.objects.create_signature(slug, request.user)

                # Use default setting if redirect_to is empty
                redirect_to = request.REQUEST.get(redirect_field_name,
                                              settings.LOGIN_REDIRECT_URL)
                # Heavier security check -- don't allow redirection to
                # a different host.
                netloc = urlparse.urlparse(redirect_to)[1]
                if netloc and netloc != request.get_host():
                    redirect_to = settings.LOGIN_REDIRECT_URL

                return HttpResponseRedirect(redirect_to)
        # In all other cases:
        context.update({'errmsg':
            'You must read and understand the terms and conditions.'})
    form = SignatureForm()
    context.update({
            redirect_field_name: request.REQUEST.get(redirect_field_name,
                                     settings.LOGIN_REDIRECT_URL)})
    context.update({'page': _read_agreement_file(slug), 'form': form})
    return render(request, "saas/agreement_sign.html", context)

