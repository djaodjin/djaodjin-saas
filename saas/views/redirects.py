# Copyright (c) 2022, DjaoDjin inc.
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
from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME, get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.views.generic import RedirectView
from django.views.generic.base import ContextMixin, TemplateResponseMixin
from django.views.generic.edit import FormMixin

from .. import settings
from ..compat import  (NoReverseMatch, gettext_lazy as _, is_authenticated,
    reverse)
from ..cart import session_cart_to_database
from ..decorators import fail_direct
from ..models import RoleDescription, get_broker
from ..utils import (get_organization_model, get_role_model,
    update_context_urls, validate_redirect_url as validate_redirect_url_base)


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


class OrganizationRedirectView(TemplateResponseMixin, ContextMixin,
                               RedirectView):
    """
    Find the ``Organization`` associated with the request user
    and return the URL that contains the organization slug
    to redirect to.
    """

    organization_model = get_organization_model()
    role_model = get_role_model()
    user_model = get_user_model()
    template_name = 'saas/organization_redirects.html'
    slug_url_kwarg = settings.PROFILE_URL_KWARG
    permanent = False
    create_more = False
    implicit_create_on_none = False
    explicit_create_on_none = False
    query_string = True

    def check_email_verified(self, request, user,
                             redirect_field_name=REDIRECT_FIELD_NAME,
                             next_url=None):
        #pylint:disable=unused-argument,no-self-use
        return True

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

    def get_implicit_grant_response(self, next_url, role, *args, **kwargs):
        #pylint:disable=unused-argument
        if role:
            organization = role.organization
            role_descr = role.role_description
            messages.info(self.request, _("Based on your e-mail address"\
                " we have granted you a %(role_descr)s role on"\
                " %(organization)s. If you need extra permissions,"\
                " contact one of the profile managers for"\
                " %(organization)s: %(managers)s.") % {
                'role_descr': role_descr.title,
                'organization': organization.printable_name,
                'managers': ', '.join([user.get_full_name() for user
                    in organization.with_role(settings.MANAGER)])})
        else:
            messages.info(self.request, _("You need to verify"\
                " your e-mail address before going further. Please"\
                " click on the link in the e-mail we just sent you."\
                " Thank you."))
        return http.HttpResponseRedirect(next_url)

    def get_natural_profile(self, request):
        """
        Returns an `Organization` which a user with `email` is naturally
        connected with (ex: same domain).
        """
        email_parts = request.user.email.lower().split('@')
        domain = email_parts[-1]
        bypass_domain = settings.BYPASS_IMPLICIT_GRANT.get('domain')
        bypass_slug = settings.BYPASS_IMPLICIT_GRANT.get('slug')
        LOGGER.debug("attempts bypass with domain %s and slug %s",
            bypass_domain, bypass_slug)
        if bypass_domain and domain == bypass_domain:
            try:
                user = self.user_model.objects.filter(
                    username=email_parts[0]).get()
            except self.user_model.DoesNotExist:
                user = request.user
            organization = self.organization_model.objects.filter(
                slug=bypass_slug).get()
            LOGGER.debug("bypass implicit grant for %s with user %s: %s",
                request.user, user, organization)
        else:
            user = request.user
            organization = self.organization_model.objects.filter(
                email__endswith=domain).get()
        return user, organization

    def get(self, request, *args, **kwargs):
        #pylint:disable=too-many-locals,too-many-statements
        #pylint:disable=too-many-nested-blocks,too-many-return-statements
        if not is_authenticated(request):
            # If we got here and the user is not authenticated, it is pointless.
            return http.HttpResponseRedirect(settings.LOGIN_URL)

        session_cart_to_database(request)

        redirect_to = reverse('saas_user_product_list', args=(request.user,))
        next_url = self.request.GET.get(REDIRECT_FIELD_NAME, None)
        if next_url:
            redirect_to += '?%s=%s' % (REDIRECT_FIELD_NAME, next_url)

        if self.role_model.objects.filter(
            user=request.user, grant_key__isnull=False).exists():
            return http.HttpResponseRedirect(redirect_to)

        accessibles = self.organization_model.objects.accessible_by(
            request.user)
        count = accessibles.count()
        if count == 0:
            # We will attempt to assign the user to a profile.
            # Find an organization with a matching e-mail domain.
            domain = request.user.email.split('@')[-1].lower()
            try:
                user, organization = self.get_natural_profile(request)
                # Find a RoleDescription we can implicitely grant to the user.
                try:
                    role_descr = RoleDescription.objects.filter(
                        Q(organization__isnull=True) |
                        Q(organization=organization),
                        implicit_create_on_none=True).get()
                    # Create a granted role implicitely, but only if the e-mail
                    # was verified.
                    next_url = validate_redirect_url_base(
                        self.request.GET.get(REDIRECT_FIELD_NAME, None),
                        sub=True, **kwargs)
                    if not next_url:
                        try:
                            next_url = self.get_redirect_url(*args, **kwargs)
                        except NoReverseMatch: # Django==2.0
                            next_url = None
                    if self.check_email_verified(request, user,
                            next_url=next_url):
                        role = organization.add_role_request(
                            user, role_descr=role_descr)
                        # We create a profile-qualified url after the role
                        # has been granted otherwise the redirect specified
                        # in the verification of e-mail will lead to a
                        # 403 permission denied.
                        kwargs.update({self.slug_url_kwarg: organization})
                        next_url = validate_redirect_url_base(
                            self.request.GET.get(REDIRECT_FIELD_NAME, None),
                            sub=True, **kwargs)
                        if not next_url:
                            try:
                                next_url = self.get_redirect_url(
                                    *args, **kwargs)
                            except NoReverseMatch: # Django==2.0
                                next_url = None
                        return self.get_implicit_grant_response(
                            next_url, role, *args, **kwargs)
                    # We are redirecting because the e-mail must be verified
                    return self.get_implicit_grant_response(
                        redirect_to, None, *args, **kwargs)
                except RoleDescription.DoesNotExist:
                    LOGGER.debug("'%s' does not have a role on any profile but"
                        " we cannot grant one implicitely because there is"
                        " no role description that permits it.",
                        user)
                except RoleDescription.MultipleObjectsReturned:
                    LOGGER.debug("'%s' does not have a role on any profile but"
                      " we cannot grant one implicitely because we have"
                      " multiple role description that permits it. Ambiguous.",
                        user)
            except self.organization_model.DoesNotExist:
                LOGGER.debug("'%s' does not have a role on any profile but"
                    " we cannot grant one implicitely because there is"
                    " no profiles with @%s e-mail domain.",
                    request.user, domain)
            except self.organization_model.MultipleObjectsReturned:
                LOGGER.debug("'%s' does not have a role on any profile but"
                    " we cannot grant one implicitely because @%s is"
                    " ambiguous. Multiple profiles share that email domain.",
                    request.user, domain)

            if self.get_implicit_create_on_none():
                try:
                    kwargs.update({self.slug_url_kwarg: str(
                        self.create_organization_from_user(request.user))})
                    return super(OrganizationRedirectView, self).get(
                        request, *args, **kwargs)
                except IntegrityError:
                    LOGGER.warning("tried to implicitely create"\
                        " an organization that already exists.",
                        extra={'request': request})
            elif self.explicit_create_on_none:
                return http.HttpResponseRedirect(redirect_to)
            raise http.Http404(_("No organizations are accessible by user."))
        if count == 1 and not self.create_more:
            organization = accessibles.get()
            kwargs.update({self.slug_url_kwarg: accessibles.get()})
            return super(OrganizationRedirectView, self).get(
                request, *args, **kwargs)
        redirects = []
        for organization in accessibles:
            kwargs.update({self.slug_url_kwarg: str(organization)})
            url = self.get_redirect_url(*args, **kwargs)
            redirects += [(url, organization.printable_name, organization.slug)]
        context = self.get_context_data(**kwargs)
        context.update({'redirects': redirects})
        update_context_urls(context, {'organization_create': redirect_to})
        return self.render_to_response(context)


class ProviderRedirectView(OrganizationRedirectView):
    """
    If the request user passes the direct relationship test
    (see ``saas.decorators.fail_direct``) with the site
    hosting provider, then redirect to it, otherwise follow
    the ``OrganizationRedirectView`` logic.
    """
    def get(self, request, *args, **kwargs):
        provider = get_broker()
        if fail_direct(request, organization=provider):
            return super(ProviderRedirectView, self).get(
                request, *args, **kwargs)
        kwargs.update({self.slug_url_kwarg: provider})
        return RedirectView.get(self, request, *args, **kwargs)


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
