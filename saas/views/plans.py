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

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.context_processors import csrf
from django.core.urlresolvers import reverse
from django.views.generic import CreateView, ListView, UpdateView
from django.views.generic.detail import SingleObjectMixin

from saas.mixins import ProviderMixin
from saas.models import CartItem, Plan
from saas.forms import PlanForm


class PlanFormMixin(ProviderMixin, SingleObjectMixin):

    model = Plan
    form_class = PlanForm

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.
        """
        kwargs = super(PlanFormMixin, self).get_initial()
        self.organization = self.get_organization()
        kwargs.update({'organization': self.organization})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(PlanFormMixin, self).get_context_data(**kwargs)
        context.update({'organization': self.organization})
        return context


class CartPlanListView(ProviderMixin, ListView):
    """
    List of plans available for subscription.
    """

    model = Plan
    template_name = 'saas/cart_plan_list.html'
    redirect_url = 'saas_cart'

    def get_queryset(self):
        queryset = Plan.objects.filter(
            organization=self.get_organization(),
            is_active=True).order_by('period_amount')
        return queryset

    def get_context_data(self, **kwargs):
        context = super(CartPlanListView, self).get_context_data(**kwargs)
        # We add the csrf token here so that javascript on the page
        # can call the shopping cart API.
        context.update(csrf(self.request))
        items_selected = []
        if self.request.user.is_authenticated():
            items_selected += [item.plan.slug
                for item in CartItem.objects.filter(user=self.request.user)]
        if self.request.session.has_key('cart_items'):
            items_selected += [item['plan']
                for item in self.request.session['cart_items']]
        context.update({'items_selected': items_selected,
            REDIRECT_FIELD_NAME: reverse(self.redirect_url)})
        return context

    def post(self, request, *args, **kwargs):
        """
        Add cliked ``Plan`` as an item in the user cart.
        """
        if 'submit' in request.POST:
            # XXX Add to Cart
            return HttpResponseRedirect(self.get_success_url())
        return self.get(request, *args, **kwargs)

    def get_success_url(self):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return redirect_path
        return reverse('saas_organization_cart')


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

