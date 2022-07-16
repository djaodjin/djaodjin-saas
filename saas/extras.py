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
from __future__ import unicode_literals

from collections import OrderedDict

from django.http import Http404
from django.shortcuts import get_object_or_404

# Implementation Note:
#
# saas.settings cannot be imported at this point because this file (extras.py)
# will be imported before ``django.conf.settings`` is fully initialized.
from .compat import (NoReverseMatch, gettext_lazy as _, is_authenticated,
    reverse, six)
from .utils import get_organization_model


class OrganizationMixinBase(object):
    """
    Returns an ``Organization`` from a URL.
    """

    organization_url_kwarg = 'organization'  # XXX PROFILE_URL_KWARG
    #organization_url_kwarg = 'profile'       # XXX PROFILE_URL_KWARG

    @property
    def organization(self):
        if not hasattr(self, '_organization'):
            self._organization = self.get_organization()
        return self._organization

    def get_organization(self):
        return get_object_or_404(get_organization_model(),
            slug=self.kwargs.get(self.organization_url_kwarg))

    def get_url_kwargs(self, **kwargs):
        """
        Rebuilds the ``kwargs`` to pass to ``reverse()``.
        """
        url_kwargs = {}
        params = kwargs if kwargs else self.kwargs
        if self.organization_url_kwarg in params:
            url_kwargs.update({self.organization_url_kwarg:
                params[self.organization_url_kwarg]})
        return url_kwargs

    def get_context_data(self, **kwargs):
        context = super(OrganizationMixinBase, self).get_context_data(**kwargs)

        organization = self.organization
        if not organization:
            # If we don't even have a broker/provider for a site.
            raise Http404(
                _("It seems a broker was not defined, or defined incorrectly."))
        context.update({'organization': organization})
        # XXX These might be moved to a higher-level
        urls = {
            'api_cart': reverse('saas_api_cart'),
            'api_redeem': reverse('saas_api_redeem_coupon'),
            'organization_create': reverse('saas_organization_create')
        }

        # URLs for both sides (subscriber and provider).
        urls.update({
            'profile_base': reverse('saas_profile'),
            'organization': {
                'api_base': reverse(
                    'saas_api_organization', args=(organization,)),
                'api_card': reverse('saas_api_card', args=(organization,)),
                'api_import': reverse(
                    'saas_api_import_transactions', args=(organization,)),
                'api_profile_base': reverse('saas_api_profile'),
                'api_profile_picture': reverse(
                    'saas_api_organization_picture', args=(organization,)),
                'api_subscriptions': reverse(
                    'saas_api_subscription_list', args=(organization,)),
                'billing_base': reverse('saas_billing_base'),
                'profile': reverse(
                    'saas_organization_profile', args=(organization,)),
        }})

        # The following `attached_user` will trigger a db query
        # even when `request.user` is anonymous.
        if organization.attached_user():
            try:
                urls['organization'].update({
                    'password_change': reverse(
                        'password_change', args=(organization,))})
            except NoReverseMatch:
                # With django.contrib.auth we cannot trigger password_change
                # for a different user than the one associated to the request.
                # It is OK. We will just not resolve the link.
                pass
        else:
            urls['organization']['roles'] = OrderedDict()
            for role_descr in organization.get_role_descriptions():
                urls['organization']['roles'].update({
                    role_descr.title: reverse('saas_role_detail',
                        args=(organization, role_descr.slug)),
                })

        # extras.py is special has it gets included before settings and models
        # are fully loaded by Django.
        from .decorators import _has_valid_access
        from .models import get_broker

        if (organization.is_provider and
            _has_valid_access(self.request, [organization, get_broker()])):
            provider = organization
            urls.update({'provider': {
                'api_bank': reverse('saas_api_bank', args=(provider,)),
                'api_coupons': reverse(
                    'saas_api_coupon_list', args=(provider,)),
                'api_metrics_plans': reverse(
                    'saas_api_metrics_plans', args=(provider,)),
                'api_plans': reverse('saas_api_plans', args=(provider,)),
                'api_receivables': reverse(
                    'saas_api_receivables', args=(provider,)),
                'api_revenue': reverse(
                    'saas_api_revenue', args=(self.organization,)),
                'api_subscribers_active': reverse(
                    'saas_api_subscribed', args=(provider,)),
                'api_subscribers_churned': reverse(
                    'saas_api_churned', args=(provider,)),
                'coupons': reverse('saas_coupon_list', args=(provider,)),
                'dashboard': reverse('saas_dashboard', args=(provider,)),
                'metrics_coupons': reverse(
                    'saas_metrics_coupons', args=(provider,)),
                'metrics_plans': reverse(
                    'saas_metrics_plans', args=(provider,)),
                'plans': reverse(
                    'saas_plan_base', args=(provider,)),
                'metrics_sales': reverse(
                    'saas_metrics_summary', args=(provider,)),
                'metrics_lifetimevalue': reverse(
                    'saas_metrics_lifetimevalue', args=(provider,)),
                'profile': reverse('saas_provider_profile'),
                'subscribers': reverse(
                    'saas_subscriber_list', args=(provider,)),
                'transfers': reverse(
                    'saas_transfer_info', args=(provider,)),
            }})
            # These might lead to 403 if provider is not broker.
            urls.update({'broker': {
                'api_users_registered': reverse('saas_api_registered'),
                'charges': reverse('saas_charges'),
            }})
            urls['organization'].update({
                'role_description': reverse('saas_role_list', args=(provider,)),
            })

        if is_authenticated(self.request):
            urls.update({'profiles': [{
                'location': reverse('saas_organization_profile',
                args=(account,)), 'printable_name': account.printable_name}
                for account in get_organization_model().objects.accessible_by(
                        self.request.user)]})

        self.update_context_urls(context, urls)
        self.update_context_urls(context, {
            'profile_redirect': reverse('accounts_profile')})

        if not organization.is_broker:
            # A broker does not have subscriptions.
            self.update_context_urls(context, {
                'organization': {
                    'billing': reverse(
                        'saas_billing_info', args=(organization,)),
                    'subscriptions': reverse(
                        'saas_subscription_list', args=(organization,)),
            }})

        return context

    @staticmethod
    def update_context_urls(context, urls):
        if 'urls' in context:
            for key, val in six.iteritems(urls):
                if key in context['urls']:
                    if isinstance(val, dict):
                        context['urls'][key].update(val)
                    else:
                        # Because organization_create url is added in this mixin
                        # and in ``OrganizationRedirectView``.
                        context['urls'][key] = val
                else:
                    context['urls'].update({key: val})
        else:
            context.update({'urls': urls})
        return context
