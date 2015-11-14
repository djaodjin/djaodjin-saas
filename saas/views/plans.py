# Copyright (c) 2015, DjaoDjin inc.
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

from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.context_processors import csrf
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.views.generic import CreateView, ListView, UpdateView
from django.views.generic.detail import SingleObjectMixin

from saas.forms import PlanForm
from saas.mixins import CartMixin, OrganizationMixin, ProviderMixin
from saas.models import CartItem, Coupon, Plan
from saas.utils import validate_redirect_url


class PlanFormMixin(OrganizationMixin, SingleObjectMixin):

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

    def get_url_kwargs(self):
        """
        Rebuilds the ``kwargs`` to pass to ``reverse()``.
        """
        url_kwargs = super(PlanFormMixin, self).get_url_kwargs()
        if hasattr(self, 'object'):
            plan_kwarg = self.object.slug
        else:
            plan_kwarg = self.kwargs['plan']
        url_kwargs.update({'plan': plan_kwarg})
        return url_kwargs


class CartPlanListView(ProviderMixin, CartMixin, ListView):
    """
    GET displays the active plans available for subscription.

    Template:

    To edit the layout of this page, create a local \
    ``saas/pricing.html`` (`example <https://github.com/djaodjin/\
djaodjin-saas/tree/master/saas/templates/saas/pricing.html>`__).

    Template context:
      - ``plan_list`` List of plans a customer can subscribed to
      - ``items_selected`` List of items currently in the request user cart.
      - ``organization`` The provider of the product
      - ``request`` The HTTP request object

    POST adds the selected plan into the request user cart.
    """

    model = Plan
    template_name = 'saas/pricing.html'
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
                for item in CartItem.objects.get_cart(self.request.user)]
        if self.request.session.has_key('cart_items'):
            items_selected += [item['plan']
                for item in self.request.session['cart_items']]
        if self.redirect_url.startswith('/'):
            redirect_url = self.redirect_url
        else:
            redirect_url = reverse(self.redirect_url)
        redeemed = self.request.session.get('redeemed', None)
        if redeemed is not None:
            redeemed = Coupon.objects.active(
                self.get_organization(), redeemed).first()
        context.update({
            'items_selected': items_selected,
            'redeemed': redeemed,
            REDIRECT_FIELD_NAME: redirect_url})
        return context

    def post(self, request, *args, **kwargs):
        """
        Add cliked ``Plan`` as an item in the user cart.
        """
        if 'submit' in request.POST:
            self.insert_item(request, plan=request.POST['submit'])
            return HttpResponseRedirect(self.get_success_url())
        return self.get(request, *args, **kwargs)

    def get_success_url(self):
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            return redirect_path
        return reverse(self.redirect_url)


class PlanCreateView(PlanFormMixin, CreateView):
    """
    Create a new ``Plan`` for an ``Organization``.

    Template:

    To edit the layout of this page, create a local \
    ``saas/profile/plans.html`` (`example <https://github.com/djaodjin/\
djaodjin-saas/tree/master/saas/templates/saas/profile/plans.html>`__).

    Template context:
      - ``organization`` The provider for the plans
      - ``request`` The HTTP request object
    """
    template_name = 'saas/profile/plans.html'

    def get_success_url(self):
        messages.success(
            self.request, "Successfully created '%s' plan." % self.object)
        return reverse('saas_metrics_plans', args=(self.organization,))


class PlanUpdateView(PlanFormMixin, UpdateView):
    """
    Update information about a ``Plan``.

    Template:

    To edit the layout of this page, create a local \
    ``saas/profile/plans.html`` (`example <https://github.com/djaodjin/\
djaodjin-saas/tree/master/saas/templates/saas/profile/plans.html>`__).

    Template context:
      - ``plan`` The plan to update
      - ``show_delete`` True if there never were subscriber to the plan
      - ``organization`` The provider of the plan
      - ``request`` The HTTP request object
    """
    template_name = 'saas/profile/plans.html'

    slug_url_kwarg = 'plan'

    def get_success_url(self):
        messages.success(
            self.request, "Successfully updated '%s' plan." % self.object)
        return reverse('saas_plan_edit', kwargs=self.get_url_kwargs())

    def get_context_data(self, **kwargs):
        context = super(PlanUpdateView, self).get_context_data(**kwargs)
        plan = self.get_object()
        context['show_delete'] = plan.subscription_set.count() == 0
        return context
