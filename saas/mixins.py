# Copyright (c) 2014, Fortylines LLC
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

import saas.backends as backend
from saas.charge import get_charge_context
from saas.models import Charge, Organization


class ChargeMixin(SingleObjectMixin):
    """
    Display a receipt for a created charge.
    """
    model = Charge
    slug_field = 'processor_id'
    slug_url_kwarg = 'charge'

    def get_object(self, queryset=None):
        charge = super(ChargeMixin, self).get_object(queryset)
        backend.pull_charge(charge)
        return charge

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
