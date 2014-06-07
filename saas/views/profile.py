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

"""Manage Profile information"""

import logging

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.views.generic import FormView, ListView, UpdateView
from django.views.generic.edit import FormMixin
from django.utils.decorators import method_decorator

from saas.forms import (OrganizationForm, ManagerAndOrganizationForm,
    UserRelationForm, UnsubscribeForm)
from saas.mixins import OrganizationMixin
from saas.models import Organization, Subscription, datetime_or_now
from saas.compat import User


LOGGER = logging.getLogger(__name__)


class ContributorListView(OrganizationMixin, ListView):
    """List of contributors to an organization."""

    paginate_by = 10
    template_name = 'saas/contributor_list.html'

    def get_queryset(self):
        self.organization = self.get_organization()
        return self.organization.contributors.all()

    def get_context_data(self, **kwargs):
        context = super(ContributorListView, self).get_context_data(**kwargs)
        context.update({'contributors': context['object_list']})
        return context


class ManagerListView(OrganizationMixin, ListView):
    """List of managers for an organization."""

    paginate_by = 10
    template_name = 'saas/manager_list.html'

    def get_queryset(self):
        self.organization = self.get_organization()
        return self.organization.managers.all()

    def get_context_data(self, **kwargs):
        context = super(ManagerListView, self).get_context_data(**kwargs)
        context.update({'managers': context['object_list']})
        return context


class SubscriberListView(OrganizationMixin, FormMixin, ListView):
    """
    List of organizations subscribed to a plan provided by the organization.
    """

    paginate_by = 10
    form_class = UnsubscribeForm
    template_name = 'saas/subscriber_list.html'

    def form_valid(self, form):
        # As long as request.user is authorized to self.get_organization(),
        # the subscription will either be valid or a 404 raised.
        self.organization = self.get_organization()
        subscription = get_object_or_404(Subscription,
            organization__slug=form.cleaned_data['subscriber'],
            plan__slug=form.cleaned_data['plan'],
            plan__organization=self.organization)
        subscription.unsubscribe_now()
        return super(SubscriberListView, self).form_valid(form)

    def get_queryset(self):
        self.organization = self.get_organization()
        return Organization.objects.filter(
            subscription__ends_at__gte=datetime_or_now(),
            subscriptions__organization=self.organization).distinct()

    def get_context_data(self, **kwargs):
        context = super(SubscriberListView, self).get_context_data(**kwargs)
        context.update({'subscribers': context['object_list']})
        return context

    def get_success_url(self):
        return reverse('saas_subscriber_list', args=(self.organization,))

    def post(self, request, *args, **kwargs): #pylint: disable=unused-argument
        # We have created a form per subscriber/plan.
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def put(self, *args, **kwargs):
        return self.post(*args, **kwargs)


class SubscriptionListView(OrganizationMixin, ListView):
    """
    List of Plans this organization is subscribed to.
    """

    model = Subscription
    paginate_by = 10
    template_name = 'saas/subscription_list.html'

    def get_queryset(self):
        self.organization = self.get_organization()
        return Subscription.objects.active_for(self.organization)

    def get_context_data(self, **kwargs):
        context = super(SubscriptionListView, self).get_context_data(**kwargs)
        context.update({'subscriptions': context['object_list']})
        return context


class OrganizationProfileView(UpdateView):

    model = Organization
    slug_url_kwarg = 'organization'
    template_name = "saas/organization_profile.html"

    def attached_manager(self):
        if self.object.managers.count() == 1:
            manager = self.object.managers.first()
            if self.object.slug == manager.username:
                return manager
        return None

    @method_decorator(transaction.atomic)
    def form_valid(self, form):
        manager = self.attached_manager()
        if manager:
            if form.cleaned_data.get('slug', None):
                manager.username = form.cleaned_data['slug']
            if form.cleaned_data['full_name']:
                name_parts = form.cleaned_data['full_name'].split(' ')
                if len(name_parts) > 1:
                    manager.first_name = name_parts[0]
                    manager.last_name = ' '.join(name_parts[1:])
                else:
                    manager.first_name = form.cleaned_data['full_name']
                    manager.last_name = ''
            if form.cleaned_data['email']:
                manager.email = form.cleaned_data['email']
            manager.save()
        return super(OrganizationProfileView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(
            OrganizationProfileView, self).get_context_data(**kwargs)
        context.update({"attached_manager": self.attached_manager()})
        return context

    def get_form_class(self):
        if self.attached_manager():
            # There is only one manager so we will add the User fields
            # to the form so they can be updated at the same time.
            return ManagerAndOrganizationForm
        return OrganizationForm

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
        return reverse('saas_contributor_list', args=(self.organization,))


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
        return reverse('saas_contributor_list', args=(self.organization,))
