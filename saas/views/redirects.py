# Copyright (c) 2025, DjaoDjin inc.
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
Helpers to redirect based on session.
"""
from __future__ import unicode_literals

import logging

from django import http
from django.conf import settings as django_settings
from django.contrib.auth import REDIRECT_FIELD_NAME, get_user_model
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.db import transaction
from django.db.models import F, Q
from django.views.generic import RedirectView, TemplateView
from django.views.generic.edit import FormMixin

from .. import settings
from ..api.serializers import AccessibleSerializer
from ..compat import is_authenticated, reverse
from ..cart import session_cart_to_database
from ..decorators import fail_direct, _valid_manager
from ..filters import SearchFilter
from ..forms import OrganizationCreateForm
from ..mixins import product_url
from ..models import CartItem, get_broker
from ..utils import (datetime_or_now, get_organization_model, get_role_model,
    get_force_personal_profile, update_context_urls,
    validate_redirect_url as validate_redirect_url_base)

LOGGER = logging.getLogger(__name__)


class RedirectFormMixin(FormMixin):
    """
    Mixin to use a redirect (i.e. ``REDIRECT_FIELD_NAME``) url when
    the form completed successfully.
    """
    success_url = django_settings.LOGIN_REDIRECT_URL

    def validate_redirect_url(self, sub=False):
        """
        Returns the next_url path if next_url matches allowed hosts.
        """
        return validate_redirect_url_base(
            self.request.GET.get(REDIRECT_FIELD_NAME, None),
            sub=sub, **self.kwargs)

    def get_success_url(self):
        next_url = self.validate_redirect_url(sub=True)
        if not next_url:
            next_url = super(RedirectFormMixin, self).get_success_url()
        return next_url

    def get_context_data(self, **kwargs):
        context = super(RedirectFormMixin, self).get_context_data(**kwargs)
        next_url = self.validate_redirect_url()
        if next_url:
            context.update({REDIRECT_FIELD_NAME: next_url})
        return context


class OrganizationRedirectView(RedirectFormMixin, TemplateView):
    """
    Find profiles accessibles by the request user, and presents a page
    with redirect options, or redirects directly to the target page if possible.

    There are two flags that alter the implemented workflow:

    - `force_personal_profile`: When this flag is set to `True`, a personal
    profile for the request user will be created (if it doesn't exist already).

    - `force_redirect_options`: When this flag is set to `True`, the page with
    redirect options will always be displayed, disabling automatic redirect
    whenever possible.
    """
    url = None
    pattern_name = None
    query_string = False
    template_name = 'saas/profile_redirects.html'
    slug_url_kwarg = settings.PROFILE_URL_KWARG
    form_class = OrganizationCreateForm
    search_fields = ('organization__slug',)

    force_personal_profile = None
    force_redirect_options = False

    organization_model = get_organization_model()
    role_model = get_role_model()
    user_model = get_user_model()

    def get_force_personal_profile(self):
        if self.force_personal_profile is None:
            return get_force_personal_profile(self.request)
        return bool(self.force_personal_profile)

    def get_redirect_url(self, request, *args, **kwargs):
        redirect_path = validate_redirect_url_base(
            request.GET.get(REDIRECT_FIELD_NAME, None), sub=True, **kwargs)
        if not redirect_path:
            # default value
            organization = kwargs.get(self.slug_url_kwarg)
            if organization:
                redirect_path = product_url(
                    subscriber=organization, request=request)
            else:
                redirect_path = reverse('product_default_start')
            # customized redirect urls
            if self.url:
                redirect_path = self.url % kwargs
            elif self.pattern_name:
                redirect_path = reverse(
                    self.pattern_name, args=args, kwargs=kwargs)
        return redirect_path


    def get(self, request, *args, **kwargs):
        #pylint:disable=too-many-locals,too-many-statements
        #pylint:disable=too-many-nested-blocks,too-many-return-statements
        if not is_authenticated(request):
            # If we got here and the user is not authenticated, it is pointless.
            return http.HttpResponseRedirect(settings.LOGIN_URL)

        at_time = datetime_or_now()

        # Store the cart in the database just that we can check for implicit
        # grants later on.
        session_cart_to_database(request)

        force_personal = (self.get_force_personal_profile() or
            CartItem.objects.get_personal_cart(request.user).exists())

        # Creates implicit grants, then accepts grants that are not
        # double-optins.
        candidates = self.role_model.objects.accessible_by(request.user,
            force_personal=force_personal, at_time=at_time)

        if force_personal:
            # We are only interested in the personal profile in this redirect,
            # or a profile that permits to buy subscriptions on behalf of other
            # profiles.
            candidates = candidates.filter(
                Q(user__username=F('organization__slug')) |
                Q(organization__is_bulk_buyer=True))

        search_filter = SearchFilter()
        candidates = search_filter.filter_queryset(request, candidates, self)
        pending_grants = candidates.filter(grant_key__isnull=False)
        accessibles = candidates.filter(
            grant_key__isnull=True, request_key__isnull=True)

        if (not self.force_redirect_options and
            not pending_grants.exists() and
            accessibles.count() == 1):
            role = accessibles.get()
            kwargs.update({self.slug_url_kwarg: str(role.organization)})
            url = self.get_redirect_url(request, *args, **kwargs)
            return http.HttpResponseRedirect(url)

        personal_profiles = dict(candidates.filter(
            user__username=F('organization__slug')).extra(select={
            'credentials': ("NOT (password LIKE '" + UNUSABLE_PASSWORD_PREFIX
            + "%%')")}).values_list('pk', 'credentials'))
        redirects = []
        serializer = AccessibleSerializer(context={'request': request})
        for role in candidates.exclude(request_key__isnull=False):
            if role.pk in personal_profiles:
                role.organization.is_personal = True
                role.organization.credentials = personal_profiles.get(role.pk)
            kwargs.update({self.slug_url_kwarg: str(role.organization)})
            role.home_url = self.get_redirect_url(request, *args, **kwargs)
            if role.grant_key:
#                redirect_to = reverse('saas_role_grant_accept',
#                    args=(role.grant_key,))
                redirect_to = reverse('saas_role_grant_accept',
                    kwargs={'verification_key': role.grant_key})
                role.home_url = "%s?%s=%s" % (redirect_to,
                    REDIRECT_FIELD_NAME, role.home_url)
            redirects += [serializer.to_representation(role)]

        context = self.get_context_data(**kwargs)
        context.update({'redirects': {'results': redirects}})
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super(OrganizationRedirectView, self).get_context_data(
            **kwargs)
        next_url = self.validate_redirect_url()
        if next_url:
            context.update({REDIRECT_FIELD_NAME: next_url})
        user = self.request.user
        update_context_urls(context, {
            'api_candidates': reverse('saas_api_search_profiles'),
            'user': {
                'api_accessibles': reverse('saas_api_accessibles', args=(
                    user,)),
                'api_profile_create': reverse('saas_api_user_profiles', args=(
                    user,)),
                'accessibles': reverse('saas_user_product_list', args=(
                    user,))
            },
        })
        return context

    def form_valid(self, form):
        with transaction.atomic():
            #pylint:disable=attribute-defined-outside-init
            self.object = form.save()
            if not _valid_manager(
                self.request.user if is_authenticated(self.request) else None,
                [get_broker()]):
                # If it is a manager of the broker platform creating
                # the newly created Organization will be accessible anyway.
                self.object.add_manager(self.request.user)
        return http.HttpResponseRedirect(self.get_success_url())

    def get_initial(self):
        kwargs = super(OrganizationRedirectView, self).get_initial()
        kwargs.update({'slug': self.request.user.username,
                       'full_name': self.request.user.get_full_name(),
                       'email': self.request.user.email})
        return kwargs

    def get_success_url(self):
        self.kwargs.update({self.slug_url_kwarg: self.object})
        success_url = self.get_redirect_url(*self.args, **self.kwargs)
        return str(success_url)


class RoleImplicitGrantAcceptView(OrganizationRedirectView):
    """
    Accept implicit role on an organization if no role exists for the user.
    """
    # XXX This class will most likely be deprecated once we are done
    # with the refactoring.


class OrganizationCreateView(OrganizationRedirectView):
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
    pattern_name = 'saas_organization_cart'
    template_name = 'saas/profile_redirects.html'
#    template_name = "saas/profile/new.html"


class ProviderRedirectView(OrganizationRedirectView):
    """
    If the request user passes the direct relationship test
    (see ``saas.decorators.fail_direct``) with the site
    hosting provider, then redirect to it, otherwise follow
    the ``OrganizationRedirectView`` logic.
    """
    def get(self, request, *args, **kwargs):
        provider = get_broker()
        if fail_direct(request, profile=provider):
            return super(ProviderRedirectView, self).get(
                request, *args, **kwargs)
        kwargs.update({self.slug_url_kwarg: provider})
        return http.HttpResponseRedirect(self.get_redirect_url(
            request, *args, **kwargs))


class UserRedirectView(RedirectView):

    slug_url_kwarg = 'user'
    pattern_name = 'users_profile'
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        """
        Find the ``User`` associated with the request user
        and return the URL that contains the username to redirect to.
        """
        kwargs.update({self.slug_url_kwarg: self.request.user.username})
        return super(UserRedirectView, self).get_redirect_url(*args, **kwargs)
