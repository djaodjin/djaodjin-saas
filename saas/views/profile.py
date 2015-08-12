# Copyright (c) 2015, DjaoDjin inc.
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

from django.conf import settings as django_settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponseRedirect
from django.views.generic import (CreateView, DetailView, ListView,
    TemplateView, UpdateView)
from django.utils.decorators import method_decorator

from saas.forms import (OrganizationForm, OrganizationCreateForm,
    ManagerAndOrganizationForm)
from saas.mixins import OrganizationMixin
from saas.models import Organization, Subscription

LOGGER = logging.getLogger(__name__)


class RoleListView(OrganizationMixin, TemplateView):
    """
    List of managers (or contributors) for an organization.

    Template:

    To edit the layout of this page, create a local \
    ``saas/profile/roles.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/profile/roles.html>`__).
    You should insure the page will call back the
    :ref:`/api/profile/:organization/roles/:role/ <api_role>`
    API end point to fetch the set of users with the specified role.

    Template context:
      - ``role`` The name of role that defines the permissions of users
        on an organization
      - ``organization`` The organization object users have permissions to.
      - ``request`` The HTTP request object
    """
    template_name = 'saas/profile/roles.html'

    def get_context_data(self, **kwargs):
        context = super(RoleListView, self).get_context_data(**kwargs)
        context.update({'role': self.kwargs.get('role', None)})
        return context


class SubscriberListView(OrganizationMixin, TemplateView):
    """
    List of organizations subscribed to a plan provided by the organization.

    Template:

    To edit the layout of this page, create a local \
    ``saas/profile/subscribers.html`` (`example <https://github.com/djaodjin/\
djaodjin-saas/tree/master/saas/templates/saas/profile/subscribers.html>`__).

    This page will typically call back
    :ref:`/api/metrics/:organization/active/ <api_metrics_subscribers_active>`
    and/or :ref:`/api/metrics/:organization/churned/\
 <api_metrics_subscribers_churned>`
    to fetch the set of active and/or churned subscribers for a provider
    plans.

    Template context:
      - ``organization`` The provider object
      - ``request`` The HTTP request object
    """

    template_name = 'saas/profile/subscribers.html'


class SubscriptionListView(OrganizationMixin, ListView):
    """
    List of Plans this organization is subscribed to.

    Template:

    To edit the layout of this page, create a local \
    ``saas/profile/subscriptions.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/profile/subscriptions.html>`__).
    You should insure the page will call back the
    :ref:`/api/profile/:organization/subscriptions/ <api_subscriptions>`
    API end point to fetch the set of subscriptions for the organization.

    Template context:
      - ``organization`` The subscriber object
      - ``request`` The HTTP request object
    """

    model = Subscription
    paginate_by = 10
    template_name = 'saas/profile/subscriptions.html'

    def get_queryset(self):
        self.organization = self.get_organization()
        return Subscription.objects.active_for(self.organization)

    def get_context_data(self, **kwargs):
        context = super(SubscriptionListView, self).get_context_data(**kwargs)
        context.update({'subscriptions': context['object_list']})
        return context


class OrganizationCreateView(CreateView):
    """
    This page helps ``User`` create a new ``Organization``. By default,
    the request user becomes a manager of the newly created entity.

    ``User`` and ``Organization`` are separate concepts links together
    by manager and contributor relationship.

    The complete ``User``, ``Organization`` and relationship might be exposed
    right away to the person registering to the site. This is very usual
    in Enterprise software.

    On the hand, a site might decide to keep the complexity hidden by
    enforcing a one-to-one manager relationship between a ``User`` (login)
    and an ``Organization`` (payment profile).

    Template:

    To edit the layout of this page, create a local \
    ``saas/app/new.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/app/new.html>`__).

    Template context:
      - ``request`` The HTTP request object
    """

    model = Organization
    form_class = OrganizationCreateForm
    pattern_name = 'saas_organization_cart'
    template_name = "saas/app/new.html"

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            self.object.add_manager(self.request.user)
        return HttpResponseRedirect(self.get_success_url())

    def get_initial(self):
        kwargs = super(OrganizationCreateView, self).get_initial()
        kwargs.update({'email': self.request.user.email})
        return kwargs

    def get_success_url(self):
        return reverse(self.pattern_name, args=(self.object,))


class DashboardView(OrganizationMixin, DetailView):
    """
    High-level dashboard for a quick glance of the business in real-time.

    Template:

    To edit the layout of this page, create a local \
    ``saas/metrics/dashboard.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/metrics/dashboard.html>`__).

    Template context:
      - ``organization`` The provider object
      - ``request`` The HTTP request object
    """

    model = Organization
    slug_url_kwarg = 'organization'
    template_name = 'saas/metrics/dashboard.html'
    steps = [
        {
            'test': 'has_profile_completed',
            'verbose_name': 'Edit profile',
            'url_name': 'saas_organization_profile'
        },
        {
            'test': 'has_plan',
            'verbose_name': 'Configure plan',
            'url_name': 'saas_plan_new'
        },
        {
            'test': 'has_bank_account',
            'verbose_name': 'Configure Bank account',
            'url_name': 'saas_update_bank'
        }
    ]

    def get_object(self, queryset=None):
        return self.get_organization()

    def get_steps(self):
        return self.steps

    def get_context_data(self, **kwargs):
        context = super(
            DashboardView, self).get_context_data(**kwargs)
        organization = self.get_organization()
        progress = 0
        next_steps = []
        steps = self.get_steps()
        for step in steps:
            if not getattr(organization, step['test']):
                step['url'] = reverse(
                    step['url_name'], kwargs=self.get_url_kwargs())
                next_steps += [step]
        progress = (len(steps) - len(next_steps)) * 100/len(steps)
        context.update({
            'progress':progress,
            'next_steps':next_steps
            })
        return context

    def get(self, request, *args, **kwargs):
        if (hasattr(django_settings, 'FEATURES_DEBUG')
            and django_settings.FEATURES_DEBUG):
            return super(DashboardView, self).get(request, *args, **kwargs)
        return HttpResponseRedirect(
            reverse('saas_metrics_summary', args=(self.get_organization(),)))


class OrganizationProfileView(OrganizationMixin, UpdateView):
    """
    Page to update contact information of an ``Organization``.

    Template:

    To edit the layout of this page, create a local \
    ``saas/profile/index.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/profile/index.html>`__).

    Template context:
      - ``attached_manager`` The sole manager of this organization if exists.
      - ``organization`` The organization object
      - ``request`` The HTTP request object
    """

    model = Organization
    slug_field = 'slug'
    slug_url_kwarg = 'organization'
    template_name = "saas/profile/index.html"

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
        kwargs.update({'is_bulk_buyer': self.object.is_bulk_buyer})
        return kwargs

    def get_success_url(self):
        messages.info(self.request, 'Profile Updated.')
        return reverse('saas_organization_profile', args=(self.object,))


