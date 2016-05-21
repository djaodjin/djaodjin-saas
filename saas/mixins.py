# Copyright (c) 2016, DjaoDjin inc.
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

import re

import dateutil
from django.core.urlresolvers import NoReverseMatch, reverse
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from django.views.generic.detail import SingleObjectMixin
from extra_views.contrib.mixins import SearchableListMixin, SortableListMixin

from . import settings
from .compat import User
from .humanize import (DESCRIBE_BUY_PERIODS, DESCRIBE_UNLOCK_NOW,
    DESCRIBE_UNLOCK_LATER, DESCRIBE_BALANCE)
from .models import (CartItem, Charge, Coupon, Organization, Plan,
    Subscription, get_broker)
from .utils import datetime_or_now, get_roles, start_of_day
from .extras import OrganizationMixinBase


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
            plan = get_object_or_404(Plan, slug=kwargs['plan'])
            queryset = CartItem.objects.get_cart(
                request.user, plan=plan).order_by('-email')
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
                                email=email, user=request.user)
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
                    plan=plan, email=email)
                if item_queryset.exists():
                    inserted_item = item_queryset.get()
                else:
                    redeemed = request.session.get('redeemed', None)
                    if redeemed:
                        redeemed = Coupon.objects.active(
                            plan.organization, redeemed).first()
                    inserted_item = CartItem.objects.create(
                        plan=plan, coupon=redeemed,
                        email=email, user=request.user,
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
    slug_field = 'processor_key'
    slug_url_kwarg = 'charge'

    def get_context_data(self, **kwargs):
        context = super(ChargeMixin, self).get_context_data(**kwargs)
        charge = self.object
        context.update(get_charge_context(charge))
        urls = {'charge': {
            'api_base': reverse('saas_api_charge', args=(charge,)),
            'api_email_receipt': reverse(
                'saas_api_email_charge_receipt', args=(charge,)),
            'api_refund': reverse('saas_api_charge_refund', args=(charge,))}}
        try:
            # optional
            urls['charge'].update({'printable_receipt': reverse(
                'saas_printable_charge_receipt',
                args=(charge.customer, charge,))})
        except NoReverseMatch:
            pass
        if 'urls' in context:
            for key, val in urls.iteritems():
                if key in context['urls']:
                    context['urls'][key].update(val)
                else:
                    context['urls'].update({key: val})
        else:
            context.update({'urls': urls})
        return context


class OrganizationMixin(OrganizationMixinBase, settings.EXTRA_MIXIN):
    pass


class BeforeMixin(object):

    clip = True
    date_field = 'created_at'

    def cache_fields(self, request):
        self.ends_at = request.GET.get('ends_at', None)
        if self.clip or self.ends_at:
            if self.ends_at is not None:
                self.ends_at = parse_datetime(self.ends_at.strip('"'))
            self.ends_at = datetime_or_now(self.ends_at)

    def get_queryset(self):
        """
        Implements before date filtering on ``date_field``
        """
        kwargs = {}
        if self.ends_at:
            kwargs.update({'%s__lt' % self.date_field: self.ends_at})
        return super(BeforeMixin, self).get_queryset().filter(**kwargs)

    def get(self, request, *args, **kwargs): #pylint: disable=unused-argument
        self.cache_fields(request)
        return super(BeforeMixin, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(BeforeMixin, self).get_context_data(**kwargs)
        if self.ends_at:
            context.update({'ends_at': self.ends_at.isoformat()})
        return context


class DateRangeMixin(BeforeMixin):

    natural_period = dateutil.relativedelta.relativedelta(months=-1)

    def cache_fields(self, request):
        super(DateRangeMixin, self).cache_fields(request)
        self.start_at = None
        if self.ends_at:
            self.start_at = request.GET.get('start_at', None)
            if self.start_at:
                self.start_at = datetime_or_now(parse_datetime(
                    self.start_at.strip('"')))
            else:
                self.start_at = (
                    start_of_day(self.ends_at + self.natural_period)
                    + dateutil.relativedelta.relativedelta(days=1))

    def get_queryset(self):
        """
        Implements date range filtering on ``created_at``
        """
        kwargs = {}
        if self.start_at:
            kwargs.update({'%s__gte' % self.date_field: self.start_at})
        return super(DateRangeMixin, self).get_queryset().filter(**kwargs)

    def get_context_data(self, **kwargs):
        context = super(DateRangeMixin, self).get_context_data(**kwargs)
        if self.start_at:
            context.update({'start_at': self.start_at.isoformat()})
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
        return get_broker()

    @staticmethod
    def get_provider():
        return get_broker()

    @property
    def provider(self):
        if not hasattr(self, '_provider'):
            self._provider = self.get_organization()
        return self._provider


class CouponMixin(ProviderMixin):
    """
    Returns a ``Coupon`` from a URL.
    """

    coupon_url_kwarg = 'coupon'

    @property
    def coupon(self):
        if not hasattr(self, '_coupon'):
            self._coupon = get_object_or_404(Coupon,
                code=self.kwargs.get(self.coupon_url_kwarg),
                organization=self.provider)
        return self._coupon

    def get_context_data(self, **kwargs):
        context = super(CouponMixin, self).get_context_data(**kwargs)
        context.update({'coupon': self.coupon})
        return context


class MetricsMixin(DateRangeMixin, ProviderMixin):

    pass


class SubscriptionMixin(object):

    model = Subscription

    def get_queryset(self):
        kwargs = {}
        start_at = self.request.GET.get('start_at', None)
        if start_at:
            start_at = datetime_or_now(parse_datetime(start_at))
            kwargs.update({'created_at__lt': start_at})
        ends_at = self.request.GET.get('ends_at', None)
        if ends_at:
            ends_at = parse_datetime(ends_at)
        ends_at = datetime_or_now(ends_at)
        return Subscription.objects.filter(
            organization__slug=self.kwargs.get('organization'),
            ends_at__gte=ends_at, **kwargs)

    def get_object(self):
        queryset = self.get_queryset()
        if 'plan' in self.kwargs:
            plan = self.kwargs.get('plan')
        else:
            plan = self.kwargs.get('subscribed_plan')
        return queryset.filter(plan__slug=plan).get()


class CartItemSmartListMixin(SortableListMixin,
                             DateRangeMixin, SearchableListMixin):
    """
    The queryset can be further filtered to a range of dates between
    ``start_at`` and ``ends_at``.

    The queryset can be further filtered by passing a ``q`` parameter.
    The value in ``q`` will be matched against:

      - user.username
      - user.first_name
      - user.last_name
      - user.email

    The result queryset can be ordered by passing an ``o`` (field name)
    and ``ot`` (asc or desc) parameter.
    The fields the queryset can be ordered by are:

      - user.first_name
      - user.last_name
      - created_at
    """
    search_fields = ['user__username',
                     'user__first_name',
                     'user__last_name',
                     'user__email']

    sort_fields_aliases = [('slug', 'user__username'),
                           ('plan', 'plan'),
                           ('created_at', 'created_at')]


class OrganizationSmartListMixin(SortableListMixin,
                                 DateRangeMixin, SearchableListMixin):
    """
    The queryset can be further filtered to a range of dates between
    ``start_at`` and ``ends_at``.

    The queryset can be further filtered by passing a ``q`` parameter.
    The value in ``q`` will be matched against:

      - slug
      - full_name
      - email
      - phone
      - street_address
      - locality
      - region
      - postal_code
      - country

    The result queryset can be ordered by passing an ``o`` (field name)
    and ``ot`` (asc or desc) parameter.
    The fields the queryset can be ordered by are:

      - full_name
      - created_at
    """
    clip = False

    search_fields = ['slug',
                     'full_name',
                     'email',
                     'phone',
                     'street_address',
                     'locality',
                     'region',
                     'postal_code',
                     'country']

    sort_fields_aliases = [('full_name', 'full_name'),
                           ('created_at', 'created_at')]


class RoleSmartListMixin(SortableListMixin,
                         DateRangeMixin, SearchableListMixin):
    """
    The queryset can be further filtered to a range of dates between
    ``start_at`` and ``ends_at``.

    The queryset can be further filtered by passing a ``q`` parameter.
    The value in ``q`` will be matched against:

      - organization.slug
      - organization.full_name
      - organization.email
      - user.username
      - user.email
      - name

    The result queryset can be ordered by passing an ``o`` (field name)
    and ``ot`` (asc or desc) parameter.
    The fields the queryset can be ordered by are:

      - full_name
      - username
      - role_name
      - created_at
    """
    search_fields = ['organization__slug',
                     'organization__full_name',
                     'organization__email',
                     'user__username',
                     'user__email',
                     'name']

    sort_fields_aliases = [('full_name', 'organization__full_name'),
                           ('username', 'user__username'),
                           ('role_name', 'name'),
                           ('created_at', 'created_at')]


class SubscriptionSmartListMixin(SortableListMixin, SearchableListMixin):
    """
    ``Subscription`` list which is also searchable and sortable.
    """
    search_fields = ['organization__slug',
                     'organization__full_name',
                     'organization__email',
                     'organization__phone',
                     'organization__street_address',
                     'organization__locality',
                     'organization__region',
                     'organization__postal_code',
                     'organization__country',
                     'plan__title']

    sort_fields_aliases = [('organization__full_name', 'organization'),
                           ('plan__title', 'plan'),
                           ('created_at', 'created_at'),
                           ('ends_at', 'ends_at')]


class UserSmartListMixin(SortableListMixin, BeforeMixin, SearchableListMixin):
    """
    ``User`` list which is also searchable and sortable.

    The queryset can be further filtered to a before date with ``ends_at``.

    The queryset can be further filtered by passing a ``q`` parameter.
    The value in ``q`` will be matched against:

      - User.first_name
      - User.last_name
      - User.email

    The result queryset can be ordered by:

      - User.first_name
      - User.last_name
      - User.email
      - User.created_at
    """
    search_fields = ['first_name',
                     'last_name',
                     'email']

    date_field = 'date_joined'

    sort_fields_aliases = [('first_name', 'first_name'),
                           ('last_name', 'last_name'),
                           ('email', 'email'),
                           ('date_joined', 'created_at')]


class ChurnedQuerysetMixin(ProviderMixin):
    """
    ``QuerySet`` of ``Subscription`` which are no longer active.
    """

    model = Subscription

    def get_queryset(self):
        kwargs = {}
        start_at = self.request.GET.get('start_at', None)
        if start_at:
            start_at = datetime_or_now(parse_datetime(start_at))
            kwargs.update({'ends_at__gte': start_at})
        ends_at = self.request.GET.get('ends_at', None)
        if ends_at:
            ends_at = parse_datetime(ends_at)
        ends_at = datetime_or_now(ends_at)
        return Subscription.objects.filter(
            plan__organization=self.provider,
            ends_at__lt=ends_at, **kwargs).order_by('-ends_at')


class SubscribedQuerysetMixin(ProviderMixin):
    """
    ``QuerySet`` of ``Subscription`` which are currently active.
    """

    model = Subscription

    def get_queryset(self):
        kwargs = {}
        start_at = self.request.GET.get('start_at', None)
        if start_at:
            start_at = datetime_or_now(parse_datetime(start_at))
            kwargs.update({'created_at__lt': start_at})
        ends_at = self.request.GET.get('ends_at', None)
        if ends_at:
            ends_at = parse_datetime(ends_at)
        ends_at = datetime_or_now(ends_at)
        return Subscription.objects.filter(
            plan__organization=self.provider,
            ends_at__gte=ends_at, **kwargs).order_by('-ends_at')


class UserMixin(object):
    """
    Returns an ``User`` from a URL.
    """
    SHORT_LIST_CUT_OFF = 8
    user_url_kwarg = 'user'

    @property
    def user(self):
        if not hasattr(self, "_user"):
            try:
                self._user = User.objects.get(
                    username=self.kwargs.get(self.user_url_kwarg))
            except User.DoesNotExist:
                self._user = self.request.user
        return self._user

    def get_context_data(self, **kwargs):
        context = super(UserMixin, self).get_context_data(**kwargs)
        user = self.user
        top_accessibles = []
        queryset = Organization.objects.accessible_by(user).filter(
            is_provider=True, is_active=True)[:self.SHORT_LIST_CUT_OFF + 1]
        for organization in queryset:
            top_accessibles += [{'printable_name': organization.printable_name,
                'location': reverse('saas_dashboard', args=(organization,))}]
        if len(queryset) > self.SHORT_LIST_CUT_OFF:
            top_accessibles += [{'printable_name': "More ...",
                'location': reverse(
                    'saas_user_product_list', args=(user,))}]
        context.update({'top_accessibles': top_accessibles})
        return context


class RelationMixin(OrganizationMixin, UserMixin):
    """
    Returns a User-Organization relation from a URL.
    """

    def get_queryset(self):
        return get_roles(self.kwargs.get('role')).filter(
            organization=self.organization, user=self.user)

    def get_object(self):
        # Since there is no lookup_field for relations, we must override
        # ``get_object``.
        queryset = self.get_queryset()
        try:
            return queryset.get()
        except queryset.model.DoesNotExist:
            #pylint:disable=protected-access
            raise Http404('No %s matches the given query.'
                % queryset.model._meta.object_name)


def as_html_description(transaction):
    """
    Add hyperlinks into a transaction description.
    """
    provider = transaction.orig_organization
    subscriber = transaction.dest_organization
    look = re.match(DESCRIBE_BUY_PERIODS % {
        'plan': r'(?P<plan>\S+)', 'ends_at': r'.*', 'humanized_periods': r'.*'},
        transaction.descr)
    if not look:
        look = re.match(DESCRIBE_UNLOCK_NOW % {
            'plan': r'(?P<plan>\S+)', 'unlock_event': r'.*'},
            transaction.descr)
    if not look:
        look = re.match(DESCRIBE_UNLOCK_LATER % {
            'plan': r'(?P<plan>\S+)', 'unlock_event': r'.*',
            'amount': r'.*'}, transaction.descr)
    if not look:
        look = re.match(DESCRIBE_BALANCE % {
            'plan': r'(?P<plan>\S+)'}, transaction.descr)
    if not look:
        # DESCRIBE_CHARGED_CARD, DESCRIBE_CHARGED_CARD_PROCESSOR
        # and DESCRIBE_CHARGED_CARD_PROVIDER.
        # are specially crafted to start with "Charge ..."
        look = re.match(r'Charge (?P<charge>\S+)', transaction.descr)
        if look:
            link = '<a href="%s">%s</a>' % (reverse('saas_charge_receipt',
                args=(subscriber, look.group('charge'),)), look.group('charge'))
            return transaction.descr.replace(look.group('charge'), link)
        return transaction.descr

    plan_link = ('<a href="%s%s/">%s</a>' % (
        product_url(provider, subscriber),
        look.group('plan'), look.group('plan')))
    return transaction.descr.replace(look.group('plan'), plan_link)


def get_charge_context(charge):
    """
    Return a dictionnary useful to populate charge receipt templates.
    """
    context = {'charge': charge,
               'charge_items': charge.line_items,
               'organization': charge.customer,
               'provider': charge.broker} # XXX update templates
    return context


def get_provider_site(provider):
    """
    Returns a Site object that contains a ``domain`` field.
    """
    if not settings.PROVIDER_SITE_CALLABLE:
        return None
    from .compat import import_string
    return import_string(settings.PROVIDER_SITE_CALLABLE)(str(provider))


def product_url(provider, subscriber=None):
    """
    We cannot use a basic ``reverse('product_default_start')`` here because
    *organization* and ``get_broker`` might be different.
    """
    current_uri = '/'
    site = get_provider_site(provider)
    if site:
        if site.domain:
            scheme = 'https' # Defaults to secure connection.
            current_uri = '%s://%s/' % (scheme, site.domain)
        else:
            current_uri += '%s/' % provider
    elif provider != get_broker():
        current_uri += '%s/' % provider
    current_uri += 'app/'
    if subscriber:
        current_uri += '%s/' % subscriber
    return current_uri
