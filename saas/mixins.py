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

from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from django.views.generic.base import ContextMixin
from django.views.generic.detail import SingleObjectMixin

from saas.compat import User
from saas.models import (CartItem, Charge, Coupon, Organization, Plan,
    Subscription, get_current_provider)
from saas.utils import datetime_or_now


def get_charge_context(charge):
    """
    Return a dictionnary useful to populate charge receipt templates.
    """
    context = {'charge': charge,
               'charge_items': charge.line_items,
               'organization': charge.customer,
               'provider': charge.provider}
    return context


class CartMixin(object):

    @staticmethod
    def insert_item(request, **kwargs):
        #pylint: disable=too-many-statements
        created = False
        inserted_item = None
        template_item = None
        email = kwargs.get('email', '')
        if request.user.is_authenticated():
            # If the user is authenticated, we just create the cart items
            # into the database.
            queryset = CartItem.objects.get_cart(
                request.user, plan__slug=kwargs['plan']).order_by('-email')
            if queryset.exists():
                template_item = queryset.first()
            if template_item:
                created = False
                inserted_item = template_item
                if email:
                    # Bulk buyer subscribes someone else than request.user
                    if template_item.email:
                        if email != template_item.email:
                            # Copy/Replace in template CartItem
                            created = True
                            inserted_item = CartItem.objects.create(
                                plan=template_item.plan,
                                coupon=template_item.coupon,
                                nb_periods=template_item.nb_periods,
                                first_name=kwargs.get('first_name', ''),
                                last_name=kwargs.get('last_name', ''),
                                email=email,
                                user=request.user)
                    else:
                        # Use template CartItem
                        inserted_item.first_name = kwargs.get('first_name', '')
                        inserted_item.last_name = kwargs.get('last_name', '')
                        inserted_item.email = email
                        inserted_item.save()
            else:
                # New CartItem
                created = True
                item_queryset = CartItem.objects.get_cart(user=request.user,
                    plan=get_object_or_404(Plan, slug=kwargs['plan']),
                    email=email)
                if item_queryset.exists():
                    inserted_item = item_queryset.get()
                else:
                    inserted_item = CartItem.objects.create(
                        email=email, user=request.user,
                        plan=get_object_or_404(Plan, slug=kwargs['plan']),
                        nb_periods=kwargs.get('nb_periods', 0),
                        first_name=kwargs.get('first_name', ''),
                        last_name=kwargs.get('last_name', ''))

        else:
            # We have an anonymous user so let's play some tricks with
            # the session data.
            cart_items = []
            if request.session.has_key('cart_items'):
                cart_items = request.session['cart_items']
            for item in cart_items:
                if item['plan'] == kwargs['plan']:
                    if not template_item:
                        template_item = item
                    elif ('email' in template_item and 'email' in item
                        and len(template_item['email']) > len(item['email'])):
                        template_item = item
            if template_item:
                created = False
                inserted_item = template_item
                if email:
                    # Bulk buyer subscribes someone else than request.user
                    if template_item.email:
                        if email != template_item.email:
                            # (anonymous) Copy/Replace in template item
                            created = True
                            cart_items += [{'plan': template_item['plan'],
                                'nb_periods': template_item['nb_periods'],
                                'first_name': kwargs.get('first_name', ''),
                                'last_name': kwargs.get('last_name', ''),
                                'email': email}]
                    else:
                        # (anonymous) Use template item
                        inserted_item['first_name'] = kwargs.get(
                            'first_name', '')
                        inserted_item['last_name'] = kwargs.get(
                            'last_name', '')
                        inserted_item['email'] = email
            else:
                # (anonymous) New item
                created = True
                cart_items += [{'plan': kwargs['plan'],
                    'nb_periods': kwargs.get('nb_periods', 0),
                    'first_name': kwargs.get('first_name', ''),
                    'last_name': kwargs.get('last_name', ''),
                    'email': email}]
            request.session['cart_items'] = cart_items
        return inserted_item, created


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

    @staticmethod
    def attached_manager(organization):
        if organization.managers.count() == 1:
            manager = organization.managers.first()
            if organization.slug == manager.username:
                return manager
        return None

    def get_organization(self):
        return get_object_or_404(Organization,
            slug=self.kwargs.get(self.organization_url_kwarg))

    def get_context_data(self, **kwargs):
        context = super(OrganizationMixin, self).get_context_data(**kwargs)
        context.update({'organization': self.get_organization()})
        return context


class ProviderMixin(OrganizationMixin):
    """
    Returns an ``Organization`` from a URL or the site owner by default.
    """

    def get_organization(self):
        if self.organization_url_kwarg in self.kwargs:
            queryset = Organization.objects.filter(
                slug=self.kwargs.get(self.organization_url_kwarg))
            if queryset.exists():
                return queryset.get()
        return get_current_provider()

    @staticmethod
    def get_provider():
        return get_current_provider()


class CouponMixin(ProviderMixin):
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


class MetricsMixin(ProviderMixin):
    """
    Adds [start_at, ends_at[ into a View instance.
    """

    def cache_fields(self, request): #pylint: disable=unused-argument
        self.organization = self.get_organization()
        self.start_at = self.request.GET.get('start_at', None)
        if self.start_at:
            self.start_at = parse_datetime(self.start_at)
        self.start_at = datetime_or_now(self.start_at)
        self.ends_at = self.request.GET.get('ends_at', None)
        print 'request', self.request.GET.get('ends_at', None)
        if self.ends_at:
            self.ends_at = parse_datetime(self.ends_at)
        print 'Ends at', self.ends_at
        self.ends_at = datetime_or_now(self.ends_at)
        print 'After datetime_or_now', self.ends_at

    def get(self, request, *args, **kwargs): #pylint: disable=unused-argument
        self.cache_fields(request)
        return super(MetricsMixin, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(MetricsMixin, self).get_context_data(**kwargs)
        context.update({'start_at': self.start_at,
                        'ends_at': self.ends_at})
        return context


class SubscriptionMixin(object):

    model = Subscription

    def get_queryset(self):
        return Subscription.objects.filter(
            organization__slug=self.kwargs.get('organization'))

    def get_object(self):
        queryset = self.get_queryset()
        if 'plan' in self.kwargs:
            plan = self.kwargs.get('plan')
        else:
            plan = self.kwargs.get('subscribed_plan')
        return queryset.filter(plan__slug=plan).get()


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

    def get_object(self):
        return get_object_or_404(self.model,
            organization=self.get_organization(), user=self.get_user())

