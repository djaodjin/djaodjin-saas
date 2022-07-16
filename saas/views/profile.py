# Copyright (c) 2021, DjaoDjin inc.
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
Manage Profile information
"""
import logging

from django import http
from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.views.generic import (CreateView, DetailView, ListView,
    TemplateView, UpdateView)

from . import RedirectFormMixin
from .. import settings, signals
from ..compat import reverse, NoReverseMatch
from ..decorators import _valid_manager
from ..forms import (OrganizationForm, OrganizationCreateForm,
    ManagerAndOrganizationForm)
from ..mixins import (OrganizationMixin, ProviderMixin, RoleDescriptionMixin,
    PlanMixin)
from ..models import Plan, Subscription, get_broker
from ..utils import (get_organization_model, update_context_urls,
    update_db_row, validate_redirect_url as validate_redirect_url_base)


LOGGER = logging.getLogger(__name__)


class RoleDetailView(RoleDescriptionMixin, TemplateView):
    """
    List of users with a specific role for an organization.

    Template:

    To edit the layout of this page, create a local \
    ``saas/profile/roles/role.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/profile/roles/role.html>`__).
    You should insure the page will call back the
    :ref:`/api/profile/:organization/roles/:role/ <api_role>`
    API end point to fetch the set of users with the specified role.

    Template context:
      - ``role_descr`` Description of the role that defines
        the permissions of users on an organization
      - ``organization`` The organization object users have permissions to.
      - ``request`` The HTTP request object
    """
    template_name = 'saas/profile/roles/role.html'

    def get_template_names(self):
        candidates = []
        role = self.kwargs.get('role', None)
        if role:
            candidates = ['saas/profile/roles/%s.html' % role]
        candidates += super(RoleDetailView, self).get_template_names()
        return candidates

    def get_context_data(self, **kwargs):
        context = super(RoleDetailView, self).get_context_data(**kwargs)
        role = self.kwargs.get('role', None)
        context.update({'role_descr': self.role_description})
        update_context_urls(context, {
            'api_candidates': reverse('saas_api_search_users'),
            'organization': {
                'api_roles': reverse(
                    'saas_api_roles_by_descr', args=(
                        self.organization, role)),
        }})
        return context


class RoleListView(OrganizationMixin, TemplateView):
    """
    List all ``RoleDescription`` for an organization and the users
    under each role.
    """

    template_name = 'saas/profile/roles/index.html'

    def get_context_data(self, **kwargs):
        context = super(RoleListView, self).get_context_data(**kwargs)
        update_context_urls(context, {'organization': {
            'api_roles': reverse(
                'saas_api_roles', args=(self.organization,)),
            'api_role_descriptions': reverse(
                'saas_api_role_description_list', args=(self.organization,)),
        }})
        return context


class SubscriberListView(ProviderMixin, TemplateView):
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

    def get_context_data(self, **kwargs):
        context = super(SubscriberListView, self).get_context_data(**kwargs)
        provider = self.provider
        tabs = [{
            "is_active": True,
            "slug": "subscribed",
            "title": "Active",
            "urls": {"download": reverse(
              'saas_subscriber_pipeline_download_subscribed', args=(provider,))
            }},
                {
            "slug": "churned",
            "title": "Churned",
            "urls": {"download": reverse(
              'saas_subscriber_pipeline_download_churned', args=(provider,))
            }}]
        context.update({'tabs': tabs})
        update_context_urls(context, {
            'subscribers_activity': reverse('saas_subscribers_activity',
            args=(provider,))
        })
        if provider.is_broker:
            update_context_urls(context, {
                'registered': {'urls': {'download': reverse(
                'saas_subscriber_pipeline_download_registered')}}})
        return context


class PlanSubscribersListView(PlanMixin, TemplateView):
    """
    GET displays the list of plan subscribers.

    Template:

    To edit the layout of this page, create a local \
    ``saas/profile/plans/subscribers.html`` (`example <https://github.com/\
djaodjin/djaodjin-saas/tree/master/saas/templates/saas/profile/plans/\
subscribers.html>`__).

    """
    template_name = 'saas/profile/plans/subscribers.html'

    def get_context_data(self, **kwargs):
        context = super(PlanSubscribersListView, self).get_context_data(
            **kwargs)
        update_context_urls(context, {
            'provider': {'api_plan_subscribers': reverse(
            'saas_api_plan_subscriptions', args=(self.provider, self.plan))}})
        return context


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
        return Subscription.objects.active_for(self.organization)

    def get_context_data(self, **kwargs):
        context = super(SubscriptionListView, self).get_context_data(**kwargs)
        context.update({'plans': Plan.objects.filter(
            organization__in=get_organization_model().objects.accessible_by(
                self.request.user, role_descr=settings.MANAGER))})
        context.update({'subscriptions': context['object_list']})
        return context


class OrganizationCreateView(RedirectFormMixin, CreateView):
    """
    This page helps ``User`` create a new ``Organization``. By default,
    the request user becomes a manager of the newly created entity.

    ``User`` and ``Organization`` are separate concepts links together
    by manager and other custom ``RoleDescription`` relationships.

    The complete ``User``, ``Organization`` and relationship might be exposed
    right away to the person registering to the site. This is very usual
    in Enterprise software.

    On the hand, a site might decide to keep the complexity hidden by
    enforcing a one-to-one manager relationship between a ``User`` (login)
    and an ``Organization`` (payment profile).

    Template:

    To edit the layout of this page, create a local \
    ``saas/profile/new.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/profile/new.html>`__).

    Template context:
      - ``request`` The HTTP request object
    """

    model = get_organization_model()
    organization_model = get_organization_model()
    organization_url_kwarg = settings.PROFILE_URL_KWARG
    form_class = OrganizationCreateForm
    pattern_name = 'saas_organization_cart'
    template_name = "saas/profile/new.html"
    implicit_create_on_none = False

    def create_organization_from_user(self, user):#pylint:disable=no-self-use
        with transaction.atomic():
            organization = self.organization_model.objects.create(
                slug=user.username,
                full_name=user.get_full_name(),
                email=user.email)
            organization.add_manager(user)
        return organization

    def get_implicit_create_on_none(self):
        return self.implicit_create_on_none

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            if not _valid_manager(self.request, [get_broker()]):
                # If it is a manager of the broker platform creating
                # the newly created Organization will be accessible anyway.
                self.object.add_manager(self.request.user)
        return http.HttpResponseRedirect(self.get_success_url())

    def get_initial(self):
        kwargs = super(OrganizationCreateView, self).get_initial()
        kwargs.update({'slug': self.request.user.username,
                       'full_name': self.request.user.get_full_name(),
                       'email': self.request.user.email})
        return kwargs

    def get_redirect_url(self, *args, **kwargs):
        #pylint:disable=unused-argument
        redirect_path = validate_redirect_url_base(
            self.request.GET.get(REDIRECT_FIELD_NAME, None), sub=True, **kwargs)
        if not redirect_path:
            try:
                redirect_path = reverse(self.pattern_name, args=(self.object,))
            except NoReverseMatch: # Django==2.0
                redirect_path = None
        return redirect_path

    def get_success_url(self):
        self.kwargs.update({self.organization_url_kwarg: self.object})
        success_url = self.get_redirect_url(*self.args, **self.kwargs)
        return str(success_url)

    def get(self, request, *args, **kwargs):
        accessibles = self.organization_model.objects.accessible_by(
            request.user)
        count = accessibles.count()
        if count == 0:
            if self.get_implicit_create_on_none():
                try:
                    self.object = self.create_organization_from_user(
                        request.user)
                    return http.HttpResponseRedirect(self.get_success_url())
                except IntegrityError:
                    LOGGER.warning("tried to implicitely create"\
                        " an organization that already exists.",
                        extra={'request': request})
        return super(OrganizationCreateView, self).get(request, *args, **kwargs)


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

    model = get_organization_model()
    slug_url_kwarg = settings.PROFILE_URL_KWARG
    template_name = 'saas/metrics/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super(DashboardView, self).get_context_data(**kwargs)
        update_context_urls(context, {
            'accounts_base': reverse('saas_profile'),
            'provider': {
                'bank': reverse('saas_update_bank', args=(self.organization,))
            }
        })
        if self.organization.is_broker:
            update_context_urls(context, {
                'provider': {
                    'api_accounts': reverse('saas_api_search_accounts')}})
        else:
            update_context_urls(context, {
                'provider': {
                    'api_accounts': reverse('saas_api_subscribers',
                        args=(self.organization,))}})
        return context

    def get_object(self, queryset=None):
        return self.organization


class OrganizationProfileView(OrganizationMixin, UpdateView):
    """
    Page to update contact information of an ``Organization``.

    Template:

    To edit the layout of this page, create a local \
    ``saas/profile/index.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/profile/index.html>`__).

    Template context:
      - ``urls.organization.password_chage`` URL to update user password.
      - ``organization`` The organization object
      - ``request`` The HTTP request object
    """

    model = get_organization_model()
    form_class = OrganizationForm
    slug_field = 'slug'
    slug_url_kwarg = settings.PROFILE_URL_KWARG
    template_name = "saas/profile/index.html"

    def update_attached_user(self, form):
        validated_data = form.cleaned_data
        user = self.object.attached_user()
        if user:
            user.username = validated_data.get('slug', user.username)
            user.email = validated_data.get('email', user.email)
            if update_db_row(user, form):
                raise ValidationError("update_attached_user")
        return user

    def form_valid(self, form):
        validated_data = form.cleaned_data
        # Calls `get_object()` such that we get the actual values present
        # in the database. `self.object` will contain the updated values
        # at this point.
        changes = self.get_object().get_changes(validated_data)
        self.object.slug = validated_data.get('slug', self.object.slug)
        self.object.full_name = validated_data['full_name']
        self.object.email = validated_data['email']
        if 'is_bulk_buyer' in validated_data:
            self.object.is_bulk_buyer = validated_data['is_bulk_buyer']
        else:
            self.object.is_bulk_buyer = False
        if 'extra' in validated_data:
            self.object.extra = validated_data['extra']
        is_provider = self.object.is_provider
        if _valid_manager(self.request, [get_broker()]):
            self.object.is_provider = validated_data.get(
                'is_provider', is_provider)

        try:
            with transaction.atomic():
                self.update_attached_user(form)
                if update_db_row(self.object, form):
                    raise ValidationError("form_valid")
        except ValidationError:
            return self.form_invalid(form)

        signals.organization_updated.send(sender=__name__,
                organization=self.object, changes=changes,
                user=self.request.user)
        return http.HttpResponseRedirect(self.get_success_url())

    def get_form_class(self):
        if self.object.attached_user():
            # There is only one user so we will add the User fields
            # to the form so they can be updated at the same time.
            return ManagerAndOrganizationForm
        return super(OrganizationProfileView, self).get_form_class()

    def get_initial(self):
        kwargs = super(OrganizationProfileView, self).get_initial()
        if Plan.objects.exists():
            # Do not display the bulk buying option if there are no plans.
            kwargs.update({'is_bulk_buyer': self.object.is_bulk_buyer})
        if _valid_manager(self.request, [get_broker()]):
            kwargs.update({
                'is_provider': self.object.is_provider,
                'extra': self.object.extra})
        return kwargs

    def get_success_url(self):
        messages.info(self.request, 'Profile updated.')
        return reverse('saas_organization_profile', args=(self.object,))
