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
Dynamic pages dealing with legal agreements.
"""

from django import forms
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.forms.widgets import CheckboxInput
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpResponseRedirect
from django.views.generic import CreateView, DetailView, ListView

from ..mixins import ProviderMixin, get_provider_site
from ..models import Agreement, Signature, get_broker
from ..utils import validate_redirect_url


class AgreementDetailView(DetailView):
    """
    Show a single agreement (or policy) document. The content of the agreement
    is read from saas/agreements/<slug>.md.

    Template:

    To edit the layout of this page, create a local \
    ``saas/legal/agreement.html`` (`example <https://github.com/djaodjin/\
djaodjin-saas/tree/master/saas/templates/saas/legal/agreement.html>`__).

    Template context:
      - ``page`` The content of the agreement formatted as HTML.
      - ``organization`` The provider of the product
      - ``request`` The HTTP request object
    """

    model = Agreement
    slug_url_kwarg = 'agreement'
    template_name = 'saas/legal/agreement.html'

    def get_context_data(self, **kwargs):
        context = super(AgreementDetailView, self).get_context_data(**kwargs)
        context.update({
                'page': _read_agreement_file(context['agreement'].slug)})
        return context


class AgreementListView(ProviderMixin, ListView):
    """
    List all agreements and policies for a provider site. This typically
    include terms of service, security policies, etc.

    Template:

    To edit the layout of this page, create a local ``saas/legal/index.html``
    (`example <https://github.com/djaodjin/djaodjin-saas/tree/master/saas/\
templates/saas/legal/index.html>`__).

    Template context:
      - ``agreement_list`` List of agreements published by the provider
      - ``organization`` The provider of the product
      - ``request`` The HTTP request object
    """

    model = Agreement
    slug_url_kwarg = 'agreement'
    template_name = 'saas/legal/index.html'

    def get_context_data(self, **kwargs):
        context = super(AgreementListView, self).get_context_data(**kwargs)
        agreements = []
        for agreement in self.get_queryset():
            agreements += [{'slug': agreement.slug, 'title': agreement.title,
                'location': reverse('legal_agreement', args=(agreement,))}]
        context['agreements'] = agreements
        return context


class SignatureForm(forms.ModelForm):
    """
    Base form to sign legal agreements.
    """

    read_terms = forms.fields.BooleanField(
        label='I have read and understand these terms and conditions',
        widget=CheckboxInput)

    class Meta:
        model = Signature
        fields = ('read_terms',)


def _read_agreement_file(slug, context=None):
    import markdown
    if not context:
        broker = get_broker()
        context = {'organization': broker}
        site = get_provider_site(broker)
        if site:
            context.update({'site': site})
    # We use context and not context=context in the following statement
    # such that the code is compatible with Django 1.7 and Django 1.8
    return markdown.markdown(
        render_to_string('saas/agreements/%s.md' % slug, context))


class AgreementSignView(ProviderMixin, CreateView):
    """
    For a the request user to sign a legal agreement.

    Template:

    To edit the layout of this page, create a local \
    ``saas/legal/sign.html`` (`example <https://github.com/djaodjin/\
djaodjin-saas/tree/master/saas/templates/saas/legal/sign.html>`__).

    Template context:
      - ``page`` The content of the agreement formatted as HTML.
      - ``organization`` The provider of the product
      - ``request`` The HTTP request object
    """
    # XXX ``ProviderMixin`` such that urls.pricing is available.

    model = Agreement
    slug_url_kwarg = 'agreement'
    template_name = 'saas/legal/sign.html'
    form_class = SignatureForm
    redirect_field_name = REDIRECT_FIELD_NAME

    def form_valid(self, form):
        if form.cleaned_data['read_terms']:
            Signature.objects.create_signature(
                self.kwargs.get(self.slug_url_kwarg), self.request.user)
            return HttpResponseRedirect(self.get_success_url())
        return self.form_invalid(form)

    def get_success_url(self):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return redirect_path
        return '/'

    def get_context_data(self, **kwargs):
        context = super(AgreementSignView, self).get_context_data(**kwargs)
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            context.update({REDIRECT_FIELD_NAME: redirect_path})
        context.update({
                'page': _read_agreement_file(self.kwargs.get('agreement'))})
        return context

