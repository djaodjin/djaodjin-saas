# Copyright (c) 2013, Fortylines LLC
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

"""Manage Profile information"""

import datetime, logging

from django.db.models import Q
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.core.context_processors import csrf
from django.shortcuts import render, redirect
from django.views.generic.list import ListView
from django.views.decorators.http import require_GET, require_POST
from django.utils.decorators import method_decorator

import saas.settings as settings
from saas.ledger import balance
from saas.forms import UserRelationForm
from saas.models import Organization, UserModel
from saas.views.auth import valid_manager_for_organization
from saas.views.auth import managed_organizations
import saas.backends as backend

LOGGER = logging.getLogger(__name__)


class OrganizationListView(ListView):
    """List of organizations the request.user is a manager for."""

    paginate_by = 10
    template_name = 'saas/managed_list.html'

    def get_queryset(self):
        return managed_organizations(self.request.user)

    def get_context_data(self, **kwargs):
        context = super(OrganizationListView, self).get_context_data(**kwargs)
        context.update({'organizations': context['object_list']})
        return context


class ContributorListView(ListView):
    """List of contributors to an organization."""

    paginate_by = 10
    template_name = 'saas/contributor_list.html'

    def get_queryset(self):
        return self.organization.contributors

    def dispatch(self, *args, **kwargs):
        self.organization = kwargs.get('organization')
        return super(ContributorListView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ContributorListView, self).get_context_data(**kwargs)
        context.update({'contributors': context['object_list']})
        return context


class ManagerListView(ListView):
    """List of managers for an organization."""

    paginate_by = 10
    template_name = 'saas/manager_list.html'

    def get_queryset(self):
        return self.organization.managers

    def dispatch(self, *args, **kwargs):
        self.organization = kwargs.get('organization')
        return super(ManagerListView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ManagerListView, self).get_context_data(**kwargs)
        context.update({'managers': context['object_list']})
        return context


class SubscriberListView(ListView):
    """
    List of organizations subscribed to a plan provided by the organization.
    """

    paginate_by = 10
    template_name = 'saas/subscriber_list.html'

    def get_queryset(self):
        return Organization.objects.filter(
            subscriptions__organization=self.organization)

    def dispatch(self, *args, **kwargs):
        self.organization = kwargs.get('organization')
        return super(SubscriberListView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(SubscriberListView, self).get_context_data(**kwargs)
        context.update({'subscribers': context['object_list']})
        return context


@require_GET
def organization_profile(request, organization):
    context = { 'user': request.user }
    context.update(csrf(request))
    balance_dues = balance(organization)
    if balance_dues < 0:
        balance_credits = - balance_dues
        balance_dues = 0
    else:
        balance_credits = None
    context.update({'organization': organization,
                    'managers': organization.managers.all(),
                    'contributors': organization.contributors.all(),
                    'balance_due': balance_dues,
                    'balance_credits': balance_credits,
                    })
    return render(request, "saas/organization_profile.html", context)


@require_POST
def organization_add_managers(request, organization):
    if request.method == 'POST':
        form = UserRelationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            organization.managers.add(
                UserModel.objects.get(username=username))
            return redirect(reverse(
                    'saas_organization_profile', args=(organization,)))
    else:
        form = UserRelationForm()
    context = { 'user': request.user,
                'organization': organization,
                'form': form,
                'call': reverse(
                    'saas_add_managers', args=(organization,)),
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
                UserModel.objects.get(username=username))
            return redirect(reverse(
                    'saas_organization_profile', args=(organization,)))
    else:
        form = UserRelationForm()
    context = { 'user': request.user,
                'organization': organization,
                'form': form,
                'call': reverse(
                    'saas_remove_managers', args=(organization,)),
                }
    context.update(csrf(request))
    return render(request, "saas/organization_user_relation.html", context)


@require_POST
def organization_add_contributors(request, organization):
    if request.method == 'POST':
        form = UserRelationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            organization.contributors.add(
                UserModel.objects.get(username=username))
            return redirect(reverse(
                    'saas_organization_profile', args=(organization,)))
    else:
        form = UserRelationForm()
    context = { 'user': request.user,
                'organization': organization,
                'form': form,
                'call': reverse(
                    'saas_add_contributors', args=(organization,)),
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
                UserModel.objects.get(username=username))
            return redirect(reverse(
                    'saas_organization_profile', args=(organization,)))
    else:
        form = UserRelationForm()
    context = { 'user': request.user,
                'organization': organization,
                'form': form,
                'call': reverse(
                    'saas_remove_contributors', args=(organization,)),
                }
    context.update(csrf(request))
    return render(request, "saas/organization_user_relation.html", context)



