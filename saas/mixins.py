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

from django.shortcuts import get_object_or_404
from django.views.generic.base import ContextMixin
from django.views.generic.detail import SingleObjectMixin

from saas.compat import User
from saas.models import Charge, Coupon, Organization


def get_charge_context(charge):
    """
    Return a dictionnary useful to populate charge receipt templates.
    """
    context = {'charge': charge,
               'charge_items': charge.charge_items.all(),
               'organization': charge.customer,
               'provider': charge.provider}
    return context


class ChargeMixin(SingleObjectMixin):
    """
    Mixin for a ``Charge`` object.
    """
    model = Charge
    slug_field = 'processor_id'
    slug_url_kwarg = 'charge'

    def get_context_data(self, **kwargs):
        context = super(ChargeMixin, self).get_context_data(**kwargs)
        context.update(get_charge_context(self.object))
        return context


class OrganizationMixin(ContextMixin):
    """
    Returns an ``Organization`` from a URL.
    """

    organization_url_kwarg = 'organization'

    def get_organization(self):
        return get_object_or_404(Organization,
            slug=self.kwargs.get(self.organization_url_kwarg))

    def get_context_data(self, **kwargs):
        context = super(OrganizationMixin, self).get_context_data(**kwargs)
        context.update({'organization': self.get_organization()})
        return context


class CouponMixin(OrganizationMixin):
    """
    Returns a ``Coupon`` from a URL.
    """

    coupon_url_kwarg = 'coupon'

    def get_coupon(self):
        return get_object_or_404(Coupon,
            code=self.kwargs.get(self.coupon_url_kwarg),
            organization=self.get_organization())

    def get_context_data(self, **kwargs):
        context = super(CouponMixin, self).get_context_data(**kwargs)
        context.update({'coupon': self.get_coupon()})
        return context


class UserMixin(ContextMixin):
    """
    Returns an ``User`` from a URL.
    """

    user_url_kwarg = 'user'

    def get_user(self):
        return get_object_or_404(User,
            username=self.kwargs.get(self.user_url_kwarg))


class RelationMixin(OrganizationMixin, UserMixin):
    """
    Returns a User-Organization relation from a URL.
    """

    def get_object(self, queryset=None): #pylint: disable=unused-argument
        return get_object_or_404(self.model,
            organization=self.get_organization(), user=self.get_user())

