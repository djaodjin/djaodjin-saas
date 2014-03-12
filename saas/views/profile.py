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
from django.core.context_processors import csrf
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic.list import ListView
from django.views.generic.edit import UpdateView
from django.views.decorators.http import require_POST

from saas import get_manager_relation_model, get_contributor_relation_model
from saas.forms import UserRelationForm
from saas.models import Organization, Plan
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

    model = Plan
    paginate_by = 10
    template_name = 'saas/subscription_list.html'

    def get_queryset(self):
        self.organization = Organization.objects.get(
            slug=self.kwargs.get('organization'))
        return self.organization.subscriptions.all()

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


@require_POST
def organization_add_managers(request, organization):
    if request.method == 'POST':
        form = UserRelationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            relation = get_manager_relation_model()(
                organization=organization,
                user=User.objects.get(username=username))
            relation.save()
            return redirect(reverse(
                    'saas_organization_profile', args=(organization,)))
    else:
        form = UserRelationForm()
    context = {'user': request.user,
               'organization': organization,
               'form': form,
               'call': reverse('saas_add_managers', args=(organization,)),
               }
    context.update(csrf(request))
    return render(request, "saas/organization_user_relation.html", context)


@require_POST
def organization_remove_managers(request, organization):
    if request.method == 'POST':
        form = UserRelationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            organization.managers.remove(
                User.objects.get(username=username))
            return redirect(reverse(
                    'saas_organization_profile', args=(organization,)))
    else:
        form = UserRelationForm()
    context = {'user': request.user,
               'organization': organization,
               'form': form,
               'call': reverse('saas_remove_managers', args=(organization,)),
               }
    context.update(csrf(request))
    return render(request, "saas/organization_user_relation.html", context)


@require_POST
def organization_add_contributors(request, organization):
    if request.method == 'POST':
        form = UserRelationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            relation = get_contributor_relation_model()(
                organization=organization,
                user=User.objects.get(username=username))
            relation.save()
            return redirect(reverse(
                    'saas_organization_profile', args=(organization,)))
    else:
        form = UserRelationForm()
    context = {'user': request.user,
               'organization': organization,
               'form': form,
               'call': reverse('saas_add_contributors', args=(organization,)),
               }
    context.update(csrf(request))
    return render(request, "saas/organization_user_relation.html", context)


@require_POST
def organization_remove_contributors(request, organization):
    if request.method == 'POST':
        form = UserRelationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            organization.contributors.remove(
                User.objects.get(username=username))
            return redirect(reverse(
                    'saas_organization_profile', args=(organization,)))
    else:
        form = UserRelationForm()
    context = {'user': request.user,
               'organization': organization,
               'form': form,
              'call': reverse('saas_remove_contributors', args=(organization,)),
               }
    context.update(csrf(request))
    return render(request, "saas/organization_user_relation.html", context)



