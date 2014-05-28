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

from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.views.generic import CreateView, ListView, UpdateView
from django.views.generic.detail import SingleObjectMixin

from saas.models import Plan, Organization
from saas.forms import PlanForm

class PlanFormMixin(SingleObjectMixin):

    model = Plan
    form_class = PlanForm

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.
        """
        kwargs = super(PlanFormMixin, self).get_initial()
        self.organization = get_object_or_404(Organization,
            slug=self.kwargs.get('organization'))
        kwargs.update({'organization': self.organization})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(PlanFormMixin, self).get_context_data(**kwargs)
        context.update({'organization': self.organization})
        return context


class CartPlanListView(ListView):
    """
    List of plans available for subscription.
    """

    model = Plan
    template_name = 'saas/cart_plan_list.html'

    def get_queryset(self):
        queryset = Plan.objects.filter(is_active=True)
        return queryset


class PlanCreateView(PlanFormMixin, CreateView):
    """
    Create a new ``Plan`` for an ``Organization``.
    """

    def get_success_url(self):
        return reverse('saas_metrics_plans', args=(self.organization,))


class PlanUpdateView(PlanFormMixin, UpdateView):
    """
    Update a new ``Plan``.
    """
    slug_url_kwarg = 'plan'

