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

import logging

from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.views.generic.base import RedirectView

from .. import settings, signals
from ..compat import gettext_lazy as _
from ..mixins import SubscriptionMixin, product_url
from ..models import get_broker
from ..utils import get_role_model, validate_redirect_url

LOGGER = logging.getLogger(__name__)


class RoleGrantAcceptView(RedirectView):

    pattern_name = 'saas_organization_profile'
    permanent = False

    @property
    def role(self):
        if not hasattr(self, '_role'):
            self._role = get_role_model().objects.filter(
                grant_key=self.kwargs.get('verification_key')).first()
        return self._role

    def get(self, request, *args, **kwargs):
        obj = self.role
        if not obj:
            # We either have a bogus `verification_key` or a `verification_key`
            # that has already been used. Either way, it is better to redirect
            # to the application page rather than showing a 404 to users
            # clicking on the link in the grant e-mail multiple times.
            return super(RoleGrantAcceptView, self).get(
                request, *args, **kwargs)

        existing_role = get_role_model().objects.filter(
            organization=obj.organization, user=request.user).exclude(
            pk=obj.pk).first()
        if existing_role:
            messages.error(request, _("You already have a %(existing_role)s"\
                " role on %(organization)s. Please drop this role first if"\
                " you want to accept a role of %(role)s instead.") % {
                    'role': obj.role_description.title,
                    'organization': obj.organization.printable_name,
                    'existing_role': existing_role.role_description.title})
            return super(RoleGrantAcceptView, self).get(
                request, *args, organization=obj.organization)

        obj.user = request.user       # We appropriate the Role here.
        grant_key = obj.grant_key
        obj.grant_key = None
        obj.save()
        LOGGER.info("%s accepted role of %s to %s (grant_key=%s)",
            request.user, obj.role_description, obj.organization,
            grant_key, extra={
                'request': request, 'event': 'accept',
                'user': str(request.user),
                'organization': str(obj.organization),
                'role_description': str(obj.role_description),
                'grant_key': grant_key})
        signals.role_grant_accepted.send(sender=__name__,
            role=obj, grant_key=grant_key, request=request)
        messages.success(request,
            _("%(role)s role to %(organization)s accepted.") % {
                'role': obj.role_description.title,
                'organization': obj.organization.printable_name})
        return super(RoleGrantAcceptView, self).get(
            request, *args, organization=obj.organization)

    def get_redirect_url(self, *args, **kwargs):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return redirect_path
        if self.role:
            return product_url(get_broker(),
                subscriber=self.role.organization, request=self.request)
        return product_url(get_broker(), request=self.request)


class SubscriptionGrantAcceptView(SubscriptionMixin, RedirectView):

    pattern_name = 'saas_organization_profile'
    permanent = False

    @property
    def subscription(self):
        if not hasattr(self, '_subscription'):
            self._subscription = self.get_queryset().filter(
                grant_key=self.kwargs.get('verification_key')).first()
        return self._subscription

    def get(self, request, *args, **kwargs):
        obj = self.subscription
        if not obj:
            # We either have a bogus `verification_key` or a `verification_key`
            # that has already been used. Either way, it is better to redirect
            # to the application page rather than showing a 404 to users
            # clicking on the link in the grant e-mail multiple times.
            return super(SubscriptionGrantAcceptView, self).get(
                request, *args, **kwargs)
        grant_key = obj.grant_key
        obj.grant_key = None
        obj.save()
        LOGGER.info("%s accepted subscription of %s to plan %s (grant_key=%s)",
            request.user, obj.organization, obj.plan,
            grant_key, extra={
                'request': request, 'event': 'accept',
                'user': str(request.user),
                'organization': str(obj.organization),
                'plan': str(obj.plan),
                'ends_at': str(obj.ends_at),
                'grant_key': grant_key})
        signals.subscription_grant_accepted.send(sender=__name__,
            subscription=obj, grant_key=grant_key, request=request)
        messages.success(request, _("Request from %(organization)s accepted.")
            % {'organization': obj.plan.organization.printable_name})
        return super(SubscriptionGrantAcceptView, self).get(
            request, *args, organization=kwargs.get('organization'))

    def get_redirect_url(self, *args, **kwargs):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return redirect_path
        if self.subscription:
            return product_url(get_broker(),
                subscriber=self.subscription.organization, request=self.request)
        return product_url(get_broker(), request=self.request)


class SubscriptionRequestAcceptView(SubscriptionMixin, RedirectView):

    pattern_name = 'saas_organization_profile'
    permanent = False
    organization_url_kwarg = settings.PROFILE_URL_KWARG

    @property
    def subscription(self):
        if not hasattr(self, '_subscription'):
            self._subscription = self.get_queryset().filter(
                request_key=self.kwargs.get('request_key')).first()
        return self._subscription

    def get(self, request, *args, **kwargs):
        obj = self.subscription
        if not obj:
            # We either have a bogus `verification_key` or a `verification_key`
            # that has already been used. Either way, it is better to redirect
            # to the application page rather than showing a 404 to users
            # clicking on the link in the grant e-mail multiple times.
            return super(SubscriptionRequestAcceptView, self).get(
                request, *args, **kwargs)
        request_key = obj.request_key
        obj.request_key = None
        obj.save()
        LOGGER.info(
            "%s accepted subscription of %s to plan %s (request_key=%s)",
            request.user, obj.organization, obj.plan,
            request_key, extra={
                'request': request, 'event': 'accept',
                'user': str(request.user),
                'organization': str(obj.organization),
                'plan': str(obj.plan),
                'ends_at': str(obj.ends_at),
                'request_key': request_key})
        signals.subscription_request_accepted.send(sender=__name__,
            subscription=obj, request_key=request_key, request=request)
        messages.success(request, _("Request from %(organization)s accepted.")
            % {'organization': obj.plan.organization.printable_name})
        return super(SubscriptionRequestAcceptView, self).get(request,
            *args, organization=kwargs.get(self.organization_url_kwarg))

    def get_redirect_url(self, *args, **kwargs):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return redirect_path
        if self.subscription:
            return product_url(get_broker(),
                subscriber=self.subscription.organization, request=self.request)
        return product_url(get_broker(), request=self.request)
