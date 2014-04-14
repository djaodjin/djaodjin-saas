# Copyright (c) 2014, Fortylines LLC
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

"""Manage Profile information"""

import logging

from django import forms
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.views.generic import FormView, ListView, UpdateView

from saas.forms import UserRelationForm
from saas.models import Organization, Subscription
from saas.compat import User


LOGGER = logging.getLogger(__name__)


class ContributorListView(ListView):
    """List of contributors to an organization."""

    paginate_by = 10
    template_name = 'saas/contributor_list.html'

    def get_queryset(self):
        self.organization = get_object_or_404(
            Organization, slug=self.kwargs.get('organization'))
        return self.organization.contributors.all()

    def get_context_data(self, **kwargs):
        context = super(ContributorListView, self).get_context_data(**kwargs)
        context.update({'organization': self.organization,
                        'contributors': context['object_list']})
        return context


class ManagerListView(ListView):
    """List of managers for an organization."""

    paginate_by = 10
    template_name = 'saas/manager_list.html'

    def get_queryset(self):
        self.organization = get_object_or_404(
            Organization, slug=self.kwargs.get('organization'))
        return self.organization.managers.all()

    def get_context_data(self, **kwargs):
        context = super(ManagerListView, self).get_context_data(**kwargs)
        context.update({'organization': self.organization,
                        'managers': context['object_list']})
        return context


class SubscriberListView(ListView):
    """
    List of organizations subscribed to a plan provided by the organization.
    """

    paginate_by = 10
    template_name = 'saas/subscriber_list.html'

    def get_queryset(self):
        self.organization = get_object_or_404(
            Organization, slug=self.kwargs.get('organization'))
        return Organization.objects.filter(
            subscriptions__organization=self.organization)

    def get_context_data(self, **kwargs):
        context = super(SubscriberListView, self).get_context_data(**kwargs)
        context.update({'organization': self.organization,
                        'subscribers': context['object_list']})
        return context


class SubscriptionListView(ListView):
    """
    List of Plans this organization is subscribed to.
    """

    model = Subscription
    paginate_by = 10
    template_name = 'saas/subscription_list.html'

    def get_queryset(self):
        self.organization = Organization.objects.get(
            slug=self.kwargs.get('organization'))
        return Subscription.objects.active_for(self.organization)

    def get_context_data(self, **kwargs):
        context = super(SubscriptionListView, self).get_context_data(**kwargs)
        context.update({'organization': self.organization,
                        'subscriptions': context['object_list']})
        return context


class OrganizationProfileForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ['full_name', 'email', 'phone', 'street_address',
                  'locality', 'region', 'postal_code',
                  'country_name']


class OrganizationProfileView(UpdateView):

    model = Organization
    form_class = OrganizationProfileForm
    slug_url_kwarg = 'organization'
    template_name = "saas/organization_profile.html"

    def get_success_url(self):
        messages.info(self.request, 'Profile Updated.')
        return reverse('saas_organization_profile', args=(self.object,))


class ManagersAdd(FormView):

    template_name = "saas/organization_user_relation.html"
    form_class = UserRelationForm

    def form_valid(self, form):
        self.organization = get_object_or_404(
            Organization, slug=self.kwargs.get('organization'))
        user = get_object_or_404(User, username=form.cleaned_data['username'])
        self.organization.add_manager(user)
        return super(ManagersAdd, self).form_valid(form)

    def get_context_data(self, **kwargs):
        self.organization = get_object_or_404(
            Organization, slug=self.kwargs.get('organization'))
        context = super(ManagersAdd, self).get_context_data(**kwargs)
        context = {'user': self.request.user,
            'organization': self.organization,
            'call': reverse(
                'saas_add_managers', args=(self.organization,))}
        return context

    def get_success_url(self):
        return reverse('saas_manager_list', args=(self.organization,))


class ManagersRemove(FormView):

    template_name = "saas/organization_user_relation.html"
    form_class = UserRelationForm

    def form_valid(self, form):
        self.organization = get_object_or_404(
            Organization, slug=self.kwargs.get('organization'))
        user = get_object_or_404(User, username=form.cleaned_data['username'])
        self.organization.remove_manager(user)
        return super(ManagersRemove, self).form_valid(form)

    def get_context_data(self, **kwargs):
        self.organization = get_object_or_404(
            Organization, slug=self.kwargs.get('organization'))
        context = super(ManagersRemove, self).get_context_data(**kwargs)
        context = {'user': self.request.user,
            'organization': self.organization,
            'call': reverse(
                'saas_remove_managers', args=(self.organization,))}
        return context

    def get_success_url(self):
        return reverse('saas_manager_list', args=(self.organization,))


class ContributorsAdd(FormView):

    template_name = "saas/organization_user_relation.html"
    form_class = UserRelationForm

    def form_valid(self, form):
        self.organization = get_object_or_404(
            Organization, slug=self.kwargs.get('organization'))
        user = get_object_or_404(User, username=form.cleaned_data['username'])
        self.organization.add_manager(user)
        return super(ContributorsAdd, self).form_valid(form)

    def get_context_data(self, **kwargs):
        self.organization = get_object_or_404(
            Organization, slug=self.kwargs.get('organization'))
        context = super(ContributorsAdd, self).get_context_data(**kwargs)
        context = {'user': self.request.user,
            'organization': self.organization,
            'call': reverse(
                'saas_add_contributors', args=(self.organization,))}
        return context

    def get_success_url(self):
        return reverse('saas_contributors_list', args=(self.organization,))


class ContributorsRemove(FormView):

    template_name = "saas/organization_user_relation.html"
    form_class = UserRelationForm

    def form_valid(self, form):
        self.organization = get_object_or_404(
            Organization, slug=self.kwargs.get('organization'))
        user = get_object_or_404(User, username=form.cleaned_data['username'])
        self.organization.remove_contributor(user)
        return super(ContributorsRemove, self).form_valid(form)

    def get_context_data(self, **kwargs):
        self.organization = get_object_or_404(
            Organization, slug=self.kwargs.get('organization'))
        context = super(ContributorsRemove, self).get_context_data(**kwargs)
        context = {'user': self.request.user,
            'organization': self.organization,
            'call': reverse(
                'saas_remove_contributors', args=(self.organization,))}
        return context

    def get_success_url(self):
        return reverse('saas_contributors_list', args=(self.organization,))
