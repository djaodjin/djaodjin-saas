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
from __future__ import unicode_literals

import logging

from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.utils.translation import ugettext_lazy as _
from django.views.generic.base import RedirectView
from rest_framework.generics import get_object_or_404

from .. import signals
from ..mixins import SubscriptionMixin
from ..utils import get_role_model, validate_redirect_url

LOGGER = logging.getLogger(__name__)


class RoleGrantAcceptView(RedirectView):

    pattern_name = 'organization_app'
    permanent = False

    @property
    def role(self):
        if not hasattr(self, '_role'):
            self._role = get_object_or_404(get_role_model().objects.all(),
                grant_key=self.kwargs.get('verification_key'))
        return self._role

    def get(self, request, *args, **kwargs):
        obj = self.role
        existing_role = get_role_model().objects.filter(
            organization=self.role.organization, user=request.user).exclude(
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
        return super(RoleGrantAcceptView, self).get_redirect_url(
            *args, **kwargs)


class SubscriptionGrantAcceptView(SubscriptionMixin, RedirectView):

    pattern_name = 'organization_app'
    permanent = False

    @property
    def subscription(self):
        if not hasattr(self, '_subscription'):
            self._subscription = get_object_or_404(self.get_queryset(),
                grant_key=self.kwargs.get('verification_key'))
        return self._subscription

    def get(self, request, *args, **kwargs):
        obj = self.subscription
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


class SubscriptionRequestAcceptView(SubscriptionMixin, RedirectView):

    pattern_name = 'organization_app'
    permanent = False

    @property
    def subscription(self):
        if not hasattr(self, '_subscription'):
            self._subscription = get_object_or_404(self.get_queryset(),
                request_key=self.kwargs.get('request_key'))
        return self._subscription

    def get(self, request, *args, **kwargs):
        obj = self.subscription
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
        return super(SubscriptionRequestAcceptView, self).get(
            request, *args, organization=kwargs.get('organization'))
