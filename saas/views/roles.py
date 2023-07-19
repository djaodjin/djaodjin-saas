# Copyright (c) 2023, DjaoDjin inc.
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
from __future__ import unicode_literals

import logging

from django import http
from django.contrib.auth import REDIRECT_FIELD_NAME, get_user_model
from django.db.models import Q
from django.views.generic.base import (ContextMixin, TemplateResponseMixin,
    RedirectView)

from .. import settings
from ..compat import reverse
from ..mixins import product_url
from ..models import RoleDescription
from ..utils import (get_organization_model, get_role_model,
    validate_redirect_url)

LOGGER = logging.getLogger(__name__)


class RoleImplicitGrantAcceptView(ContextMixin, TemplateResponseMixin,
                                  RedirectView):
    """
    Accept implicit role on an organization if no role exists for the user.
    """
    permanent = False
    slug_url_kwarg = settings.PROFILE_URL_KWARG
    role_model = get_role_model()
    user_model = get_user_model()
    organization_model = get_organization_model()
    template_name = 'saas/users/roles/accept.html'

    def check_email_verified(self, request, user,
                             redirect_field_name=REDIRECT_FIELD_NAME,
                             next_url=None):
        #pylint:disable=unused-argument
        return True


    def get_implicit_grant_response(self, next_url, role, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context.update({REDIRECT_FIELD_NAME: next_url})
        if role:
            context.update({
                'role': role,
                'contacts': ', '.join([user.get_full_name() for user
                    in role.organization.with_role(settings.MANAGER).exclude(
                    pk=self.request.user.pk)])
            })
        return self.render_to_response(context)


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
            organization = \
                self.organization_model.objects.find_candidates_by_domain(
                domain).get()
        return user, organization

    def get_redirect_url(self, *args, **kwargs):
        # XXX copy/pasted from `RoleGrantAcceptView`
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None), sub=True, **kwargs)
        if not redirect_path:
            organization = kwargs.get(self.slug_url_kwarg)
            if organization:
                redirect_path = product_url(subscriber=organization,
                    request=self.request)
            else:
                redirect_path = reverse('product_default_start')
        return redirect_path

    def get(self, request, *args, **kwargs):
        redirect_to = reverse('saas_user_product_list', args=(request.user,))
        next_to = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if next_to:
            redirect_to += '?%s=%s' % (REDIRECT_FIELD_NAME, next_to)

        # If there are no roles associated to the user, we will attempt
        # to assign the user to a profile with a matching e-mail domain.
        is_email_verified = True  # If there is a role, we don't force
                                  # verification of the e-mail address.
        if not self.role_model.objects.filter(user=self.request.user).exists():
            # In all cases, we verify the user has access to the e-mail account.
            next_url = self.get_redirect_url(*args, **kwargs)
            is_email_verified = self.check_email_verified(request, request.user,
                next_url=next_url)
            # XXX copy/pasted from `OrganizationRedirectView`
            domain = request.user.email.split('@')[-1].lower()
            try:
                user, organization = self.get_natural_profile(request)
                # Find a RoleDescription we can implicitely grant to the user.
                try:
                    if organization.get_roles().exists():
                        role_descr = RoleDescription.objects.filter(
                            Q(organization__isnull=True) |
                            Q(organization=organization),
                            implicit_create_on_none=True).get()
                    else:
                        # If this profile is not yet claimed by any user,
                        # then we implicitely grant a manager role.
                        role_descr = organization.get_role_description(
                            settings.MANAGER)
                    # Create a granted role implicitely, but only if the e-mail
                    # was verified.
                    if is_email_verified:
                        role = organization.add_role_request(
                            user, role_descr=role_descr)
                        if role.request_key:
                            # We have done an implicit grant of a manager role.
                            role.request_key = None
                            role.save()
                        # We create a profile-qualified url after the role
                        # has been granted otherwise the redirect specified
                        # in the verification of e-mail will lead to a
                        # 403 permission denied.
                        kwargs.update({self.slug_url_kwarg: organization})
                        next_url = self.get_redirect_url(*args, **kwargs)
                        return self.get_implicit_grant_response(
                            next_url, role, *args, **kwargs)
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
        if not is_email_verified:
            # We are redirecting because the e-mail must be verified
            return self.get_implicit_grant_response(
                redirect_to, None, *args, **kwargs)
        # XXX This one must return to users/roles/!!!
        return http.HttpResponseRedirect(redirect_to)
