# Copyright (c) 2018, DjaoDjin inc.
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

import logging, re

from django import http
from django.conf import settings as django_settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.db import IntegrityError, transaction
from django.http.request import split_domain_port, validate_host
from django.shortcuts import get_object_or_404
from django.utils import six
from django.utils.translation import ugettext_lazy as _
from django.views.generic import RedirectView
from django.views.generic.base import ContextMixin, TemplateResponseMixin
from django.views.generic.edit import FormMixin, ProcessFormView

from .. import settings
from ..compat import reverse, NoReverseMatch
from ..decorators import fail_direct
from ..models import CartItem, Coupon, Plan, Organization, get_broker
from ..utils import update_context_urls


LOGGER = logging.getLogger(__name__)


def session_cart_to_database(request):
    """
    Transfer all the items in the cart stored in the session into proper
    records in the database.
    """
    claim_code = request.GET.get('code', None)
    if claim_code:
        with transaction.atomic():
            cart_items = CartItem.objects.by_claim_code(claim_code)
            for cart_item in cart_items:
                cart_item.user = request.user
                cart_item.save()
    if 'cart_items' in request.session:
        with transaction.atomic():
            for item in request.session['cart_items']:
                coupon = item.get('coupon', None)
                option = item.get('option', 0)
                full_name = item.get('full_name', '')
                sync_on = item.get('sync_on', '')
                email = item.get('email', '')
                # We use ``filter(...).first()`` instead of ``get_or_create()``
                # here just in case the database is inconsistent and multiple
                # ``CartItem`` are already present.
                cart_item = CartItem.objects.get_cart(
                    user=request.user, plan__slug=item['plan']).filter(
                    full_name=full_name, email=email, sync_on=sync_on).first()
                # if the item is already in the cart, it is OK to forget about
                # any additional count of it. We are just going to constraint
                # the available one further.
                if cart_item:
                    updated = False
                    if coupon and not cart_item.coupon:
                        cart_item.coupon = coupon
                        updated = True
                    if option and not cart_item.option:
                        cart_item.option = option
                        updated = True
                    if full_name and not cart_item.full_name:
                        cart_item.full_name = full_name
                        updated = True
                    if sync_on and not cart_item.sync_on:
                        cart_item.sync_on = sync_on
                        updated = True
                    if email and not cart_item.email:
                        cart_item.email = email
                        updated = True
                    if updated:
                        cart_item.save()
                else:
                    plan = get_object_or_404(Plan, slug=item['plan'])
                    CartItem.objects.create(
                        user=request.user, plan=plan,
                        full_name=full_name, email=email,
                        sync_on=sync_on, coupon=coupon,
                        option=option)
            del request.session['cart_items']
    redeemed = request.session.get('redeemed', None)
    if redeemed:
        # When the user has selected items while anonymous, this step
        # could be folded into the previous transaction. None-the-less
        # plain and stupid is best here. We apply redeemed coupons
        # either way (anonymous or not).
        with transaction.atomic():
            CartItem.objects.redeem(request.user, redeemed)
            del request.session['redeemed']

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
        next_url = self.request.GET.get(REDIRECT_FIELD_NAME, None)
        if not next_url:
            return None
        parts = six.moves.urllib.parse.urlparse(next_url)
        if parts.netloc:
            domain, _ = split_domain_port(parts.netloc)
            allowed_hosts = (['*'] if django_settings.DEBUG
                else django_settings.ALLOWED_HOSTS)
            if not (domain and validate_host(domain, allowed_hosts)):
                return None
        path = parts.path
        if sub:
            try:
                # We replace all ':slug/' by '%(slug)s/' so that we can further
                # create an instantiated url through Python string expansion.
                path = re.sub(r':(%s)/' % settings.ACCT_REGEX,
                    r'%(\1)s/', path) % self.kwargs
            except KeyError:
                # We don't have all keys necessary. A safe defaults is to remove
                # them. Most likely a redirect URL is present to pick between
                # multiple choices.
                path = re.sub(r'%(\S+)s/', '', path)
        return six.moves.urllib.parse.urlunparse(("", "", path,
            parts.params, parts.query, parts.fragment))

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

    template_name = 'saas/organization_redirects.html'
    slug_url_kwarg = 'organization'
    permanent = False
    create_more = False
    implicit_create_on_none = False
    explicit_create_on_none = False
    query_string = True

    def create_organization_from_user(self, user):#pylint:disable=no-self-use
        with transaction.atomic():
            organization = Organization.objects.create(
                slug=user.username,
                full_name=user.get_full_name(),
                email=user.email)
            organization.add_manager(user)
        return organization

    def get_implicit_create_on_none(self):
        return self.implicit_create_on_none

    def get(self, request, *args, **kwargs):
        session_cart_to_database(request)
        accessibles = Organization.objects.accessible_by(request.user)
        count = accessibles.count()
        try:
            next_url = self.get_redirect_url(*args, **kwargs)
        except NoReverseMatch: # Django==2.0
            next_url = None
        if next_url:
            create_url = '%s?next=%s' % (
                reverse('saas_organization_create'), next_url)
        else:
            create_url = reverse('saas_organization_create')
        if count == 0:
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
                return http.HttpResponseRedirect(create_url)
            raise http.Http404(_("No organizations are accessible by user."))
        if count == 1 and not self.create_more:
            organization = accessibles.get()
            kwargs.update({self.slug_url_kwarg: accessibles.get()})
            return super(OrganizationRedirectView, self).get(
                request, *args, **kwargs)
        redirects = []
        for organization in accessibles:
            kwargs.update({self.slug_url_kwarg: organization})
            url = super(OrganizationRedirectView, self).get_redirect_url(
                *args, **kwargs)
            redirects += [(url, organization.printable_name, organization.slug)]
        context = self.get_context_data(**kwargs)
        context.update({'redirects': redirects})
        update_context_urls(context, {'organization_create': create_url})
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
