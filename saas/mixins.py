# Copyright (c) 2019, DjaoDjin inc.
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

#pylint:disable=too-many-lines
from __future__ import unicode_literals

import re

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.db.models import Q, F
from django.http import Http404
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext_lazy as _
from django.views.generic.detail import SingleObjectMixin
from rest_framework.generics import get_object_or_404

from . import settings
from .compat import NoReverseMatch, is_authenticated, reverse
from .filters import DateRangeFilter, OrderingFilter, SearchFilter
from .humanize import (as_money, DESCRIBE_BUY_PERIODS, DESCRIBE_BUY_USE,
    DESCRIBE_UNLOCK_NOW, DESCRIBE_UNLOCK_LATER, DESCRIBE_BALANCE)
from .models import (CartItem, Charge, Coupon, Organization, Plan,
    RoleDescription, Subscription, Transaction, UseCharge, get_broker)
from .utils import (build_absolute_uri, datetime_or_now, is_broker,
    get_organization_model, get_role_model, update_context_urls)
from .extras import OrganizationMixinBase


class CartMixin(object):

    @staticmethod
    def insert_item(request, **kwargs):
        #pylint: disable=too-many-statements,too-many-nested-blocks
        #pylint: disable=too-many-locals
        created = False
        inserted_item = None
        template_item = None
        invoice_key = kwargs.get('invoice_key')
        sync_on = kwargs.get('sync_on', '')
        option = kwargs.get('option', 0)
        email = kwargs.get('email', '')
        plan = kwargs['plan']
        if not isinstance(plan, Plan):
            plan = get_object_or_404(Plan.objects.all(), slug=plan)
        use = kwargs.get('use', None)
        if use and not isinstance(use, UseCharge):
            use = get_object_or_404(UseCharge.objects.filter(
                plan=plan), slug=use)
        if is_authenticated(request):
            # If the user is authenticated, we just create the cart items
            # into the database.
            queryset = CartItem.objects.get_cart(
                request.user, plan=plan).order_by('-sync_on')
            if queryset.exists():
                template_item = queryset.first()
            if template_item:
                created = False
                inserted_item = template_item
                if sync_on:
                    account = queryset.filter(email=email)
                    if account.exists():
                        inserted_item = template_item = account.first()

                    template_option = template_item.option
                    if option > 0:
                        template_option = option
                    # Bulk buyer subscribes someone else than request.user
                    if template_item.sync_on:
                        if sync_on != template_item.sync_on:
                            # Copy/Replace in template CartItem
                            created = True
                            inserted_item = CartItem.objects.create(
                                user=request.user,
                                plan=template_item.plan,
                                use=template_item.use,
                                coupon=template_item.coupon,
                                option=template_option,
                                full_name=kwargs.get('full_name', ''),
                                sync_on=sync_on,
                                email=email,
                                claim_code=invoice_key)
                    else:
                        # Use template CartItem
                        inserted_item.full_name = kwargs.get('full_name', '')
                        inserted_item.option = template_option
                        inserted_item.sync_on = sync_on
                        inserted_item.email = email
                        inserted_item.save()
                else:
                    # Use template CartItem
                    inserted_item.full_name = kwargs.get('full_name', '')
                    inserted_item.option = option
                    inserted_item.save()
            else:
                # New CartItem
                created = True
                item_queryset = CartItem.objects.get_cart(user=request.user,
                    plan=plan, sync_on=sync_on)
                # TODO this conditional is not necessary: at this point
                # we have already checked that there is no such CartItem, right?
                if item_queryset.exists():
                    inserted_item = item_queryset.get()
                else:
                    redeemed = request.session.get('redeemed', None)
                    if redeemed:
                        redeemed = Coupon.objects.active(
                            plan.organization, redeemed).first()
                    inserted_item = CartItem.objects.create(
                        plan=plan, use=use, coupon=redeemed,
                        user=request.user,
                        option=option,
                        full_name=kwargs.get('full_name', ''),
                        sync_on=sync_on, claim_code=invoice_key)

        else:
            # We have an anonymous user so let's play some tricks with
            # the session data.
            cart_items = []
            if 'cart_items' in request.session:
                cart_items = request.session['cart_items']
            for item in cart_items:
                if item['plan'] == str(plan):
                    if not template_item:
                        template_item = item
                    elif ('sync_on' in template_item and 'sync_on' in item
                      and len(template_item['sync_on']) > len(item['sync_on'])):
                        template_item = item
            if template_item:
                created = False
                inserted_item = template_item
                if sync_on:
                    # Bulk buyer subscribes someone else than request.user
                    if template_item.sync_on:
                        if sync_on != template_item.sync_on:
                            # (anonymous) Copy/Replace in template item
                            created = True
                            cart_items += [{'plan': template_item['plan'],
                                'use': template_item['use'],
                                'option': template_item['option'],
                                'full_name': kwargs.get('full_name', ''),
                                'sync_on': sync_on,
                                'email': email,
                                'invoice_key': invoice_key}]
                    else:
                        # (anonymous) Use template item
                        inserted_item['full_name'] = kwargs.get(
                            'full_name', '')
                        inserted_item['sync_on'] = sync_on
                        inserted_item['email'] = email
            else:
                # (anonymous) New item
                created = True
                cart_items += [{'plan': str(plan), 'use': str(use),
                    'option': kwargs.get('option', 0),
                    'full_name': kwargs.get('full_name', ''),
                    'sync_on': sync_on,
                    'email': email,
                    'invoice_key': invoice_key}]
            request.session['cart_items'] = cart_items
        return inserted_item, created

    @staticmethod
    def get_invoicable_options(subscription, created_at=None,
                               prorate_to=None, cart_item=None):
        """
        Return a set of lines that must charged Today and a set of choices
        based on current subscriptions that the user might be willing
        to charge Today.
        """
        #pylint: disable=too-many-locals
        created_at = datetime_or_now(created_at)
        option_items = []
        plan = subscription.plan
        # XXX Not charging setup fee, it complicates the design too much
        # at this point.

        # Pro-rated to billing cycle
        prorated_amount = 0
        if prorate_to:
            prorated_amount = plan.prorate_period(created_at, prorate_to)

        discount_percent = 0
        descr_suffix = None
        if cart_item:
            coupon = cart_item.coupon
            if coupon:
                discount_percent = coupon.percent
                if coupon.code.startswith('cpn_'):
                    descr_suffix = ', complimentary of %s' % cart_item.full_name
                else:
                    descr_suffix = '(code: %s)' % coupon.code

        first_periods_amount = plan.first_periods_amount(
            discount_percent=discount_percent,
            prorated_amount=prorated_amount)

        if first_periods_amount == 0:
            # We are having a freemium business models, no discounts.
            if not descr_suffix:
                descr_suffix = _("free")
            option_items += [Transaction.objects.new_subscription_order(
                subscription, 1, prorated_amount, created_at,
                discount_percent=discount_percent,
                descr_suffix=descr_suffix)]

        elif plan.unlock_event:
            # Locked plans are free until an event.
            option_items += [Transaction.objects.new_subscription_order(
                subscription, 1, plan.period_amount, created_at,
                DESCRIBE_UNLOCK_NOW % {
                    'plan': plan, 'unlock_event': plan.unlock_event},
               discount_percent=discount_percent,
               descr_suffix=descr_suffix)]
            option_items += [Transaction.objects.new_subscription_order(
                subscription, 1, 0, created_at,
                DESCRIBE_UNLOCK_LATER % {
                        'amount': as_money(plan.period_amount, plan.unit),
                        'plan': plan, 'unlock_event': plan.unlock_event})]

        else:
            natural_periods = plan.natural_options()
            for nb_periods in natural_periods:
                if nb_periods > 1:
                    descr_suffix = ""
                    amount, discount_percent \
                        = subscription.plan.advance_period_amount(nb_periods)
                    if amount <= 0:
                        break # never allow to be completely free here.
                option_items += [Transaction.objects.new_subscription_order(
                    subscription, nb_periods, prorated_amount, created_at,
                    discount_percent=discount_percent,
                    descr_suffix=descr_suffix)]

        return option_items

    def as_invoicables(self, user, customer, at_time=None):
        """
        Returns a list of invoicables from the cart of a request user.

        invoicables = [
                { "subscription": Subscription,
                  "lines": [Transaction, ...],
                  "options": [Transaction, ...],
                }, ...]


        Each subscription is either an actual record in the database (paying
        more periods on a subscription) or ``Subscription`` instance that only
        exists in memory but will be committed on checkout.

        The ``Transaction`` list keyed by "lines" contains in-memory instances
        for the invoice items that will be committed and charged when the order
        is finally placed.

        The ``Transaction`` list keyed by "options" contains in-memory instances
        the user can choose from. Options usually include various number
        of periods that can be pre-paid now for a discount. ex:

        $189.00 Subscription to medium-plan until 2015/11/07 (1 month)
        $510.30 Subscription to medium-plan until 2016/01/07 (3 months, 10% off)
        $907.20 Subscription to medium-plan until 2016/04/07 (6 months, 20% off)
        """
        #pylint: disable=too-many-locals
        created_at = datetime_or_now(at_time)
        prorate_to_billing = False
        prorate_to = None
        if prorate_to_billing:
            # XXX First we add enough periods to get the next billing date later
            # than created_at but no more than one period in the future.
            prorate_to = customer.billing_start
        invoicables = []
        for cart_item in CartItem.objects.get_cart(user=user):
            for_descr = ''
            organization = customer
            if cart_item.sync_on:
                full_name = cart_item.full_name.strip()
                for_descr = ', for %s (%s)' % (full_name, cart_item.sync_on)
                organization_queryset = Organization.objects.filter(
                    Q(slug=cart_item.sync_on)
                    | Q(email__iexact=cart_item.sync_on))
                if organization_queryset.exists():
                    organization = organization_queryset.get()
                else:
                    user_queryset = get_user_model().objects.filter(
                        Q(username=cart_item.sync_on)
                        | Q(email__iexact=cart_item.sync_on))
                    if not user_queryset.exists():
                        # XXX Hacky way to determine GroupBuy vs. notify.
                        organization = Organization(
                            full_name=cart_item.full_name,
                            email=cart_item.sync_on)
            try:
                # If we can extend a current ``Subscription`` we will.
                # XXX For each (organization, plan) there should not
                #     be overlapping timeframe [created_at, ends_at[,
                #     None-the-less, it might be a good idea to catch
                #     and throw a nice error message in case.
                subscription = Subscription.objects.get(
                    organization=organization, plan=cart_item.plan,
                    ends_at__gt=datetime_or_now())
            except Subscription.DoesNotExist:
                ends_at = prorate_to
                if not ends_at:
                    ends_at = created_at
                subscription = Subscription.objects.new_instance(
                    organization, cart_item.plan, ends_at=ends_at)
            lines = []
            options = []
            if cart_item.use:
                # We are dealing with an additional use charge instead
                # of the base subscription.
                lines += [Transaction.objects.new_use_charge(subscription,
                    cart_item.use, cart_item.option)]
            else:
                options = self.get_invoicable_options(subscription,
                    created_at=created_at, prorate_to=prorate_to,
                    cart_item=cart_item)
                # option is selected
                if (cart_item.option > 0 and
                    (cart_item.option - 1) < len(options)):
                    # The number of periods was already selected so we generate
                    # a line instead.
                    line = options[cart_item.option - 1]
                    lines += [line]
                    options = []
            # Both ``TransactionManager.new_use_charge``
            # and ``TransactionManager.new_subscription_order`` will have
            # created a ``Transaction`` with the ultimate subscriber
            # as payee. Overriding ``dest_organization`` here
            # insures in all cases (bulk and direct buying),
            # the transaction is recorded (in ``execute_order``)
            # on behalf of the customer on the checkout page.
            for line in lines:
                line.dest_organization = customer
                line.descr += for_descr
            invoicables += [{
                'name': cart_item.name, 'descr': cart_item.descr,
                'subscription': subscription,
                "lines": lines, "options": options}]
        return invoicables


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
        update_context_urls(context, urls)
        return context


class UserMixin(object):
    """
    Returns an ``User`` from a URL.
    """
    SHORT_LIST_CUT_OFF = 8
    user_url_kwarg = 'user'

    @property
    def user(self):
        if not hasattr(self, '_user'):
            self._user = None
            username = self.kwargs.get(self.user_url_kwarg, None)
            if username:
                user_model = get_user_model()
                try:
                    self._user = user_model.objects.get(username=username)
                except user_model.DoesNotExist:
                    pass
            elif is_authenticated(self.request):
                self._user = self.request.user
        return self._user

    def get_context_data(self, **kwargs):
        context = super(UserMixin, self).get_context_data(**kwargs)
        if self.user:
            top_accessibles = []
            queryset = Organization.objects.accessible_by(self.user).filter(
                is_active=True).exclude(
                slug=self.user.username)[:self.SHORT_LIST_CUT_OFF + 1]
            for organization in queryset:
                if organization.is_provider:
                    location = reverse('saas_dashboard', args=(organization,))
                else:
                    location = reverse('saas_organization_profile',
                        args=(organization,))
                top_accessibles += [{
                    'slug': organization.slug,
                    'printable_name': organization.printable_name,
                    'location': location}]
            if len(queryset) > self.SHORT_LIST_CUT_OFF:
                # XXX Always add link to "More..." so a user can request access.
                top_accessibles += [{
                    'slug': None,
                    'printable_name': _("More ..."),
                    'location': reverse(
                        'saas_user_product_list', args=(self.user,))}]
            context.update({'top_accessibles': top_accessibles})
            update_context_urls(context, {
                'user': {
                    'accessibles': reverse('saas_user_product_list',
                        args=(self.user,))
            }})
            try:
                # optional (see signup.mixins.UserMixin)
                update_context_urls(context, {
                'user': {
                    'notifications': reverse(
                        'users_notifications', args=(self.user,)),
                    'profile': reverse('users_profile', args=(self.user,)),
                }})
            except NoReverseMatch:
                pass

        update_context_urls(context, {
            'profile_base': reverse('saas_profile'),
            'profile_redirect': reverse('accounts_profile')})
        return context


class OrganizationMixin(OrganizationMixinBase, settings.EXTRA_MIXIN):

    pass


class OrganizationDecorateMixin(object):

    @staticmethod
    def as_organization(user):
        organization = get_organization_model()(
            slug=user.username, email=user.email,
            full_name=user.get_full_name(), created_at=user.date_joined)
        organization.user = user
        return organization

    @staticmethod
    def decorate_personal(page):
        # Adds a boolean `is_personal` if there exists a User such that
        # `Organization.slug == User.username`.
        # Implementation Note:
        # The SQL we wanted to generate looks like the following.
        #
        # SELECT slug,
        #   (Count(slug=username) > 0) AS is_personal
        #   (Count(slug=username
        #      AND NOT (password LIKE '!%')) > 0) AS credentials
        # FROM saas_organization LEFT OUTER JOIN (
        #   SELECT organization_id, username FROM auth_user INNER JOIN saas_role
        #   ON auth_user.id = saas_role.user_id) AS roles
        # ON saas_organization.id = roles.organization_id
        # GROUP BY saas_organization.id;
        #
        # I couldn't figure out a way to get Django ORM to do this. The closest
        # attempts was
        #    queryset = get_organization_model().objects.annotate(
        #        Count('role__user__username')).extra(
        #        select={'is_personal': "count(slug=username) > 0"})
        #
        # Unfortunately that adds `is_personal` and `credentials` to the GROUP
        # BY clause, which leads to an exception.
        #
        # The UNION implementation below cannot be furthered filtered
        # (https://docs.djangoproject.com/en/2.2/ref/models/querysets/#union)
        #personal_qs = get_organization_model().objects.filter(
        #    role__user__username=F('slug')).extra(select={'is_personal': 1,
        #    'credentials':
        #        "NOT (password LIKE '" + UNUSABLE_PASSWORD_PREFIX + "%%')"})
        #organization_qs = get_organization_model().objects.exclude(
        #    role__user__username=F('slug')).extra(select={'is_personal': 0,
        #    'credentials': 0})
        #queryset = personal_qs.union(organization_qs)
        #
        # A raw query cannot be furthered filtered either.
        organization_model = get_organization_model()
        records = [page] if isinstance(page, organization_model) else page
        personal = dict(organization_model.objects.filter(
            pk__in=[profile.pk for profile in records if profile.pk],
            role__user__username=F('slug')).extra(select={
            'credentials': ("NOT (password LIKE '" + UNUSABLE_PASSWORD_PREFIX
            + "%%')")}).values_list('pk', 'credentials'))
        for profile in records:
            if profile.pk in personal:
                profile.is_personal = True
                profile.credentials = personal[profile.pk]
        return page


class DateRangeContextMixin(object):

    forced_date_range = True

    @property
    def start_at(self):
        if not hasattr(self, '_start_at'):
            self._start_at = self.request.GET.get('start_at', None)
            if self._start_at:
                self._start_at = datetime_or_now(self._start_at.strip('"'))
        return self._start_at

    @property
    def ends_at(self):
        if not hasattr(self, '_ends_at'):
            self._ends_at = self.request.GET.get('ends_at', None)
            if self.forced_date_range or self._ends_at:
                if self._ends_at is not None:
                    self._ends_at = self._ends_at.strip('"')
                self._ends_at = datetime_or_now(self._ends_at)
        return self._ends_at

    @property
    def timezone(self):
        if not hasattr(self, '_timezone'):
            self._timezone = self.request.GET.get('timezone', None)
        return self._timezone

    def get_context_data(self, **kwargs):
        context = super(DateRangeContextMixin, self).get_context_data(**kwargs)
        if self.start_at:
            context.update({'start_at': self.start_at})
        if self.ends_at:
            context.update({'ends_at': self.ends_at})
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


class PlanMixin(ProviderMixin):

    model = Plan
    plan_url_kwarg = 'plan'

    @property
    def plan(self):
        if not hasattr(self, '_plan'):
            self._plan = get_object_or_404(Plan.objects.all(),
                slug=self.kwargs.get(self.plan_url_kwarg),
                organization=self.provider)
        return self._plan

    @staticmethod
    def slugify(title):
        slug_base = slugify(title)
        i = 0
        slug = slug_base
        while Plan.objects.filter(slug__exact=slug).count() > 0:
            slug = slugify('%s-%d' % (slug_base, i))
            i += 1
        return slug


class CouponMixin(ProviderMixin):
    """
    Returns a ``Coupon`` from a URL.
    """

    coupon_url_kwarg = 'coupon'

    @property
    def coupon(self):
        if not hasattr(self, '_coupon'):
            self._coupon = get_object_or_404(
                Coupon.objects.filter(organization=self.provider),
                code=self.kwargs.get(self.coupon_url_kwarg))
        return self._coupon

    def get_context_data(self, **kwargs):
        context = super(CouponMixin, self).get_context_data(**kwargs)
        context.update({'coupon': self.coupon})
        return context


class MetricsMixin(DateRangeContextMixin, ProviderMixin):

    filter_backends = (DateRangeFilter,)


class SubscriptionMixin(OrganizationDecorateMixin):

    model = Subscription
    subscriber_url_kwarg = 'organization'

    def get_queryset(self):
        kwargs = {}
        state = self.request.GET.get('state')
        if state:
            today = datetime_or_now()
            if state == 'active':
                kwargs.update({'ends_at__gt': today})
            elif state == 'expired':
                kwargs.update({'ends_at__lt': today})
        else:
            starts_at = self.request.GET.get('expires_after')
            ends_at = self.request.GET.get('expires_before')
            #tz = self.request.GET.get('timezone')
            if starts_at:
                starts_at = datetime_or_now(starts_at)
                kwargs.update({'ends_at__gt': starts_at})
            if ends_at:
                ends_at = datetime_or_now(ends_at)
                kwargs.update({'ends_at__lt': ends_at})
        # Use ``filter`` instead of active_for here because we want to list
        # through the API subscriptions which are pending opt-in.
        return Subscription.objects.filter(
            organization__slug=self.kwargs.get(self.subscriber_url_kwarg),
            **kwargs)

    def paginate_queryset(self, queryset):
        page = super(SubscriptionMixin, self).paginate_queryset(
            queryset)
        self.decorate_personal([sub.organization for sub in page])
        return page

    def get_object(self):
        queryset = self.get_queryset()
        if 'plan' in self.kwargs:
            plan = self.kwargs.get('plan')
        else:
            plan = self.kwargs.get('subscribed_plan')
        obj = get_object_or_404(queryset, plan__slug=plan)
        self.decorate_personal(obj.organization)
        return obj


class CartItemSmartListMixin(object):
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
    search_fields = ('user__username',
                     'user__first_name',
                     'user__last_name',
                     'user__email')

    ordering_fields = [('slug', 'user__username'),
                           ('plan', 'plan'),
                           ('created_at', 'created_at')]

    filter_backends = (DateRangeFilter, OrderingFilter, SearchFilter)


class OrganizationSmartListMixin(object):
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
    forced_date_range = False

    alternate_fields = {
        'slug': 'username',
        'full_name': ('first_name', 'last_name'),
        'created_at': 'date_joined',
    }

    search_fields = (
        'slug',
        'full_name',
        'email',
        'phone',
        'street_address',
        'locality',
        'region',
        'postal_code',
        'country',
        # fields in User model:
        'username',
        'first_name',
        'last_name')

    ordering_fields = (
        'full_name',
        'created_at')

    # XXX technically we should derive ('first_name', 'last_name')
    # from `alternate_fields` but it complicates the implementation
    # of `OrderingFilter.get_ordering`:
    #     ```ordering = self.remove_invalid_fields(
    #            queryset, self.get_default_ordering(view), view, request)```
    ordering = ('full_name', 'first_name', 'last_name')

    filter_backends = (DateRangeFilter, SearchFilter, OrderingFilter)


class RoleSmartListMixin(object):
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
      - role_description.title
      - role_description.slug

    The result queryset can be ordered by passing an ``o`` (field name)
    and ``ot`` (asc or desc) parameter.
    The fields the queryset can be ordered by are:

      - full_name
      - username
      - role_name
      - created_at
    """
    search_fields = (
        'organization__slug',
        'organization__full_name',
        'organization__email',
        'user__username',
        'user__email',
        'role_description__title',
        'role_description__slug'
    )
    ordering_fields = [
        ('organization__full_name', 'full_name'),
        ('user__username', 'username'),
        ('role_description__title', 'role_name'),
        ('grant_key', 'grant_key'),
        ('request_key', 'request_key'),
        ('created_at', 'created_at')
    ]
    ordering = ('user__username',)

    filter_backends = (DateRangeFilter, SearchFilter, OrderingFilter)


class SubscriptionSmartListMixin(object):
    """
    ``Subscription`` list which is also searchable and sortable.
    """
    search_fields = ('organization__slug',
                     'organization__full_name',
                     'organization__email',
                     'organization__phone',
                     'organization__street_address',
                     'organization__locality',
                     'organization__region',
                     'organization__postal_code',
                     'organization__country',
                     'plan__title')

    ordering_fields = [('organization__full_name', 'organization'),
                           ('plan__title', 'plan'),
                           ('created_at', 'created_at'),
                           ('ends_at', 'ends_at')]

    ordering = ('ends_at',)

    filter_backends = (OrderingFilter, SearchFilter)


class UserSmartListMixin(object):
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
    search_fields = ('first_name',
                     'last_name',
                     'email')

    ordering_fields = [('first_name', 'first_name'),
                           ('last_name', 'last_name'),
                           ('email', 'email'),
                           ('date_joined', 'created_at')]

    filter_backends = (DateRangeFilter, OrderingFilter, SearchFilter)


class SubscribersQuerysetMixin(OrganizationDecorateMixin, ProviderMixin):

    model = Subscription

    def get_queryset(self):
        # OK to use ``filter`` here since we want to list all subscriptions.
        return Subscription.objects.filter(
            plan__organization=self.provider)

    def paginate_queryset(self, queryset):
        page = super(SubscribersQuerysetMixin, self).paginate_queryset(
            queryset)
        self.decorate_personal([sub.organization for sub in page])
        return page


class PlanSubscribersQuerysetMixin(PlanMixin, SubscribersQuerysetMixin):

    def get_queryset(self):
        return super(PlanSubscribersQuerysetMixin, self).get_queryset().filter(
            plan__slug=self.kwargs.get(self.plan_url_kwarg))


class ChurnedQuerysetMixin(DateRangeContextMixin, SubscribersQuerysetMixin):
    """
    ``QuerySet`` of ``Subscription`` which are no longer active.
    """

    filter_backends = (DateRangeFilter,)

    def get_queryset(self):
        queryset = super(ChurnedQuerysetMixin, self).get_queryset()
        kwargs = {}
        start_at = self.request.GET.get('start_at', None)
        if start_at:
            # We don't want to constraint the start date if it is not
            # explicitely set.
            kwargs.update({'ends_at__gte': self.start_at})
        return queryset.valid_for(
            ends_at__lt=self.ends_at, **kwargs).order_by('-ends_at')


class SubscribedQuerysetMixin(DateRangeContextMixin, SubscribersQuerysetMixin):
    """
    ``QuerySet`` of ``Subscription`` which are currently active.

    Optionnaly when an ``ends_at`` query parameter is specified,
    returns a ``QuerySet`` of ``Subscription`` that were active
    at ``ends_at``.

    Optionnaly when a ``start_at`` query parameter is specified,
    only considers ``Subscription`` that were created after ``start_at``.
    """

    model = Subscription
    filter_backends = (DateRangeFilter,)

    def get_queryset(self):
        queryset = super(SubscribedQuerysetMixin, self).get_queryset()
        kwargs = {}
        start_at = self.request.GET.get('start_at', None)
        if start_at:
            # We don't want to constraint the start date if it is not
            # explicitely set.
            kwargs.update({'created_at__lt': self.start_at})
        return queryset.active_with(
            self.provider, ends_at=self.ends_at, **kwargs).order_by('-ends_at')


class RoleDescriptionMixin(OrganizationMixin):

    @property
    def role_description(self):
        if not hasattr(self, '_role_description'):
            try:
                self._role_description = self.organization.get_role_description(
                    self.kwargs.get('role'))
            except RoleDescription.DoesNotExist:
                raise Http404(_("RoleDescription '%(role)s' does not exist.")
                    % {'role': self.kwargs.get('role')})
        return self._role_description


class RoleMixin(RoleDescriptionMixin):
    """
    Returns a User-Organization relation from a URL.

    It is used in Role APIs.
    """
    user_url_kwarg = 'user'

    @property
    def user(self):
        if not hasattr(self, '_user'):
            self._user = get_object_or_404(get_user_model().objects.all(),
                username=self.kwargs.get(self.user_url_kwarg))
        return self._user

    def get_queryset(self):
        try:
            if self.kwargs.get('role'):
                kwargs = {'role_description': self.role_description}
            else:
                kwargs = {}
        except RoleDescription.DoesNotExist:
            kwargs = {}
        # OK to use filter here since we want to present all pending grants
        # and requests.
        return get_role_model().objects.filter(
            organization=self.organization, user=self.user, **kwargs)

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
    result = transaction.descr

    # DESCRIBE_CHARGED_CARD, DESCRIBE_CHARGED_CARD_PROCESSOR
    # and DESCRIBE_CHARGED_CARD_PROVIDER.
    # are specially crafted to start with "Charge ..."
    look = re.match(r'Charge (?P<charge>\S+)', transaction.descr)
    if look:
        link = '<a href="%s">%s</a>' % (reverse('saas_charge_receipt',
            args=(transaction.dest_organization
                  if transaction.dest_account == Transaction.EXPENSES
                  else transaction.orig_organization, look.group('charge'),)),
            look.group('charge'))
        result = result.replace(look.group('charge'), link)

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
        look = re.match(DESCRIBE_BUY_USE % {
            'quantity': r'\d+',
            'use_charge': r'.*',
            'plan': r'(?P<plan>\S+)'}, transaction.descr)
    if not look:
        look = re.match(r'.*for (?P<subscriber>\S+):(?P<plan>\S+)',
            transaction.descr)
        if look:
            subscriber = look.group('subscriber')
            if str(transaction.orig_organization) == subscriber:
                provider = transaction.dest_organization
            else:
                provider = transaction.orig_organization
            link = '<a href="%s">%s</a>' % (reverse('saas_organization_profile',
                args=(subscriber,)), subscriber)
            result = result.replace(subscriber, link)
    if look:
        plan_link = ('<a href="%s%s/">%s</a>' % (
            product_url(provider, subscriber),
            look.group('plan'), look.group('plan')))
        result = result.replace(look.group('plan'), plan_link)
    return result


def get_charge_context(charge):
    """
    Return a dictionnary useful to populate charge receipt templates.
    """
    context = {'charge': charge,
               'refunded': charge.refunded.exists(),
               'charge_items': charge.line_items,
               'organization': charge.customer,
               'provider': charge.broker, # XXX update templates
    }
    return context


def product_url(provider, subscriber=None, request=None):
    """
    We cannot use a basic ``reverse('product_default_start')`` here because
    *organization* and ``get_broker`` might be different.
    """
    location = '/app/'
    if subscriber:
        location += '%s/' % subscriber
    if settings.BUILD_ABSOLUTE_URI_CALLABLE:
        return build_absolute_uri(request, location=location, provider=provider)
    elif not is_broker(provider):
        location = '/%s' % provider + location
    return location
