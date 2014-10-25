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
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, UpdateView
from django.views.generic.edit import FormMixin
from django.utils.decorators import method_decorator
from extra_views import SearchableListMixin, SortableListMixin

from saas.forms import (OrganizationForm, ManagerAndOrganizationForm,
    UnsubscribeForm)
from saas.mixins import OrganizationMixin, ProviderMixin
from saas.models import Organization, Subscription, datetime_or_now

LOGGER = logging.getLogger(__name__)


class ContributorListBaseView(ListView):
    """
    List of contributors for an organization.

    Must be used with an OrganizationMixin or a ProviderMixin.
    """

    paginate_by = 10
    template_name = 'saas/contributor_list.html'

    # Make pylint happy: ``get_organization`` will be picked up correctly
    # in the derived classes.
    def get_organization(self):
        return self

    def get_queryset(self):# XXX not necessary since we use a REST API,
                           # yet need to find out to get the pagination correct.
        self.organization = self.get_organization()
        return self.organization.contributors.all()


class ProviderContributorListView(ProviderMixin, ContributorListBaseView):
    """
    List of contributors for the site provider.
    """
    pass


class ContributorListView(OrganizationMixin, ContributorListBaseView):
    """
    List of contributors for an organization.
    """
    pass


class ManagerListBaseView(ListView):
    """
    List of managers for an organization.

    Must be used with an OrganizationMixin or a ProviderMixin.
    """

    paginate_by = 10
    template_name = 'saas/manager_list.html'

    # Make pylint happy: ``get_organization`` will be picked up correctly
    # in the derived classes.
    def get_organization(self):
        return self

    def get_queryset(self):# XXX not necessary since we use a REST API,
                           # yet need to find out to get the pagination correct.
        self.organization = self.get_organization()
        return self.organization.managers.all()


class ProviderManagerListView(ProviderMixin, ManagerListBaseView):
    """
    List of managers for the site provider.
    """
    pass


class ManagerListView(OrganizationMixin, ManagerListBaseView):
    """
    List of managers for an organization.
    """
    pass


class SubscriberListBaseView(ProviderMixin, ListView):

    model = Subscription

    def get_queryset(self):
        self.organization = self.get_organization()
        queryset = super(SubscriberListBaseView, self).get_queryset().filter(
            ends_at__gte=datetime_or_now(),
            plan__organization=self.organization).distinct()
        return queryset


class SmartListMixin(SearchableListMixin, SortableListMixin):
    """
    Subscriber list which is also searchable and sortable.
    """
    search_fields = ['organization__full_name',
                     'organization__email',
                     'organization__phone',
                     'organization__street_address',
                     'organization__locality',
                     'organization__region',
                     'organization__postal_code',
                     'organization__country']

    sort_fields_aliases = [('organization__full_name', 'full_name'),
                           ('plan__title', 'plan'),
                           ('created_at', 'since'),
                           ('ends_at', 'ends_at')]

    def get_context_data(self, **kwargs):
        context = super(
            SmartListMixin, self).get_context_data(**kwargs)
        context.update({'q': self.request.GET.get('q', '')})
        return context

    def get_template_names(self):
        """
        Return a list of template names to be used for the request. Must return
        a list. May not be called if render_to_response is overridden.
        """
        names = []
        if self.sort_helper.initial_sort:
            if hasattr(self.object_list, 'model'):
                #pylint: disable=protected-access
                opts = self.object_list.model._meta
                names.append("%s/%s_sort_by_%s%s.html" % (
                    opts.app_label, opts.model_name,
                    self.sort_helper.sort_fields[self.sort_helper.initial_sort],
                    self.template_name_suffix))
        try:
            names += super(
                SmartListMixin, self).get_template_names()
        except ImproperlyConfigured:
            pass
        return names


class SubscriberListView(SmartListMixin, FormMixin, SubscriberListBaseView):
    """
    List of organizations subscribed to a plan provided by the organization.
    """

    paginate_by = 25
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


class OrganizationProfileView(OrganizationMixin, UpdateView):

    model = Organization
    slug_field = 'slug'
    slug_url_kwarg = 'organization'
    template_name = "saas/organization_profile.html"

    @method_decorator(transaction.atomic)
    def form_valid(self, form):
        if 'is_bulk_buyer' in form.cleaned_data:
            self.object.is_bulk_buyer = form.cleaned_data['is_bulk_buyer']
        else:
            self.object.is_bulk_buyer = False
        manager = self.attached_manager(self.object)
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
        context.update({"attached_manager": self.attached_manager(self.object)})
        return context

    def get_form_class(self):
        if self.attached_manager(self.object):
            # There is only one manager so we will add the User fields
            # to the form so they can be updated at the same time.
            return ManagerAndOrganizationForm
        return OrganizationForm

    def get_initial(self):
        kwargs = super(OrganizationProfileView, self).get_initial()
        queryset = Organization.objects.providers_to(
            self.object).filter(managers__id=self.request.user.id)
        if queryset.exists():
            kwargs.update({'is_bulk_buyer': self.object.is_bulk_buyer})
        return kwargs

    def get_success_url(self):
        messages.info(self.request, 'Profile Updated.')
        return reverse('saas_organization_profile', args=(self.object,))


class ProviderProfileView(ProviderMixin, OrganizationProfileView):

    def get_object(self, queryset=None):
        return self.get_organization()

    def get_success_url(self):
        messages.info(self.request, 'Profile Updated.')
        return reverse('saas_provider_profile',)
