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

#pylint:disable=too-many-lines
from __future__ import unicode_literals

import logging, re

from django.contrib.auth import REDIRECT_FIELD_NAME, get_user_model
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.db import models, transaction, IntegrityError
from django.http import Http404
from django.template.defaultfilters import slugify
from rest_framework.generics import get_object_or_404

from . import humanize, settings
from .cart import cart_insert_item
from .compat import (NoReverseMatch, gettext_lazy as _, is_authenticated,
    reverse, six)
from .filters import DateRangeFilter, OrderingFilter, SearchFilter
from .models import (CartItem, Charge, Coupon, Plan, Price,
    RoleDescription, Subscription, Transaction, get_broker, is_broker,
    sum_orig_amount)
from .utils import (build_absolute_uri, datetime_or_now,
    full_name_natural_split, get_organization_model, get_role_model,
    handle_uniq_error, update_context_urls, validate_redirect_url)
from .extras import OrganizationMixinBase

LOGGER = logging.getLogger(__name__)


class BalanceDueMixin(object):
    """
    Mixin to retrieve a profile's balance due as line items
    for a checkout workflow.
    """
    @staticmethod
    def get_balance_options(subscription, created_at=None,
                               prorate_to=None, cart_item=None):
        #pylint: disable=unused-argument
        options = []
        payable = Transaction.objects.new_subscription_statement(
            subscription, created_at)
        if payable.dest_amount > 0:
            later = Transaction.objects.new_subscription_later(
                subscription, created_at)
            options = [payable, later]
        return options

    def as_invoicables(self, user, customer, at_time=None):
        #pylint: disable=too-many-locals,unused-argument,no-self-use
        invoicables = []
        at_time = datetime_or_now(at_time)
        balances = Transaction.objects.get_statement_balances(
            customer, until=at_time)
        for event_id, amount_by_units in six.iteritems(balances):
            if not event_id.startswith('sub_'):
                # XXX Not showing balance due on group buy events.
                LOGGER.error("Looking at a balance %s on event_id '%s'",
                    amount_by_units, event_id)
                continue
            subscription = Subscription.objects.get_by_event_id(event_id)
            last_unpaid_orders = customer.last_unpaid_orders(
                subscription=subscription, at_time=at_time)
            order_balances = sum_orig_amount(last_unpaid_orders)
            lines = []
            for order_balance in order_balances:
                order_amount = order_balance.get('amount')
                balance_amount = amount_by_units.get(order_balance.get('unit'))
                if order_amount == balance_amount:
                    lines = last_unpaid_orders
                    break
            options = []
            if not lines:
                # XXX paying balance due is not optional.
                #options = self.get_balance_options(
                #    subscription, created_at=at_time)
                lines = [Transaction.objects.new_subscription_statement(
                    subscription, at_time)]
            if lines or options:
                invoicables += [{
                    'subscription': subscription,
                    'name': 'cart-%s' % subscription.plan.slug,
                    'lines': lines,
                    'options': options}]
        return invoicables


class CartMixin(object):
    """
    Mixin to retrieve a user's cart as line items for a checkout workflow.
    """

    def insert_item(self, request, at_time=None, **kwargs):
        cart_item, created = cart_insert_item(request, **kwargs)
        detail = None
        # insert_item will either return a dict or a CartItem instance
        # (which cannot be directly serialized).
        if isinstance(cart_item, CartItem):
            try:
                invoicable = self.cart_item_as_invoicable(
                    cart_item, at_time=at_time)
                if (not invoicable.get('options') and
                    len(invoicable.get('lines', [])) == 1):
                    detail = invoicable['lines'][0].descr
            except get_organization_model().DoesNotExist:
                detail = None
            cart_item.detail = detail
        return cart_item, created

    def get_cart(self):
        """
        returns the items currently in the cart.
        """
        if is_authenticated(self.request):
            return [{
                'plan': cart_item.plan.slug,
                'use': cart_item.use,
                'option': cart_item.option,
                'full_name': cart_item.full_name,
                'sync_on': cart_item.sync_on,
                'email': cart_item.email,
                'invoice_key': cart_item.claim_code
            } for cart_item in CartItem.objects.get_cart(
                user=self.request.user)]
        if 'cart_items' in self.request.session:
            return self.request.session['cart_items']
        return []


    @staticmethod
    def get_cart_options(subscription, created_at=None,
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
        full_amount = prorated_amount + plan.period_amount

        coupon = cart_item.coupon if cart_item else None

        discount_by_types = {}
        coupon_discount_amount = 0
        if coupon:
            coupon_discount_amount = coupon.get_discount_amount(
                prorated_amount=prorated_amount,
                period_amount=plan.period_amount)
            discount_by_types[coupon.discount_type] = coupon.discount_value
        amount = full_amount - coupon_discount_amount
        if amount <= 0:
            amount = 0

        if plan.unlock_event:
            # Locked plans are free until an event.
            option_items += [Transaction.objects.new_subscription_order(
                subscription,
                amount=amount,
                descr=humanize.DESCRIBE_UNLOCK_NOW % {
                    'plan': plan, 'unlock_event': plan.unlock_event},
                created_at=created_at)]
            option_items += [Transaction.objects.new_subscription_order(
                subscription,
                amount=0,
                descr=humanize.DESCRIBE_UNLOCK_LATER % {
                        'amount': humanize.as_money(
                            plan.period_amount, plan.unit),
                        'plan': plan, 'unlock_event': plan.unlock_event},
                created_at=created_at)]

        else:
            ends_at = plan.end_of_period(
                subscription.ends_at, plan.period_length)
            option_items += [Transaction.objects.new_subscription_order(
                subscription,
                amount=amount,
                descr=humanize.describe_buy_periods(
                    plan, ends_at, 1,
                    discount_by_types=discount_by_types,
                    coupon=coupon,
                    cart_item=cart_item),
                created_at=created_at)]

            advance_discounts = plan.advance_discounts.all().order_by('length')
            for advance_discount in advance_discounts:
                full_amount = (
                    prorated_amount + advance_discount.full_periods_amount)
                advance_discount_amount = advance_discount.get_discount_amount(
                    prorated_amount=prorated_amount)
                discount_by_types = {}
                discount_by_types[advance_discount.discount_type] = \
                    advance_discount.discount_value
                coupon_discount_amount = 0
                if coupon:
                    coupon_discount_amount = coupon.get_discount_amount(
                        prorated_amount=prorated_amount,
                        period_amount=plan.period_amount,
                        advance_amount=(advance_discount.full_periods_amount
                            - plan.period_amount))
                    if coupon.discount_type in discount_by_types:
                        discount_by_types[coupon.discount_type] += \
                            coupon.discount_value
                    else:
                        discount_by_types[coupon.discount_type] = \
                            coupon.discount_value
                amount = (full_amount - advance_discount_amount
                    - coupon_discount_amount)
                if amount <= 0:
                    continue # never allow to be completely free here.
                nb_periods = (
                    advance_discount.length * plan.period_length)
                ends_at = plan.end_of_period(subscription.ends_at, nb_periods)
                option_items += [Transaction.objects.new_subscription_order(
                    subscription,
                    amount=amount,
                    descr=humanize.describe_buy_periods(
                        plan, ends_at, nb_periods,
                        discount_by_types=discount_by_types,
                        coupon=coupon,
                        cart_item=cart_item),
                    created_at=created_at)]

        return option_items

    def cart_item_as_invoicable(self, cart_item, customer=None, at_time=None):
        created_at = datetime_or_now(at_time)
        prorate_to_billing = False
        prorate_to = None
        if prorate_to_billing:
            # XXX First we add enough periods to get the next billing date later
            # than created_at but no more than one period in the future.
            prorate_to = customer.billing_start
        subscriber = customer
        organization_model = get_organization_model()
        if cart_item.sync_on:
            try:
                subscriber = organization_model.objects.get(
                    models.Q(slug=cart_item.sync_on)
                    | models.Q(email__iexact=cart_item.sync_on))
            except organization_model.DoesNotExist:
                # commit c30c4c58 states "not a groupbuy when sync_on is
                # a username"
                user_queryset = get_user_model().objects.filter(
                    models.Q(username=cart_item.sync_on)
                    | models.Q(email__iexact=cart_item.sync_on))
                if not user_queryset.exists():
                    # XXX Hacky way to determine GroupBuy vs. notify.
                    subscriber = get_organization_model()(
                        full_name=cart_item.full_name.strip(),
                        email=cart_item.sync_on)
        if not subscriber:
            # We cannot figure out a subscriber from the cart_item
            # and not profile was passed as a customer to be billed.
            raise organization_model.DoesNotExist()
        try:
            # If we can extend a current ``Subscription`` we will.
            # XXX For each (organization, plan) there should not
            #     be overlapping timeframe [created_at, ends_at[,
            #     None-the-less, it might be a good idea to catch
            #     and throw a nice error message in case.
            subscription = Subscription.objects.get(
                organization=subscriber, plan=cart_item.plan,
                ends_at__gt=created_at)
        except Subscription.DoesNotExist:
            ends_at = prorate_to if prorate_to else created_at
            subscription = Subscription.objects.new_instance(
                subscriber, cart_item.plan, ends_at=ends_at)
        lines = []
        options = []
        if cart_item.use:
            # We are dealing with an additional use charge instead
            # of the base subscription.
            lines += [Transaction.objects.new_use_charge(subscription,
                cart_item.use, cart_item.option)]
        else:
            options = self.get_cart_options(subscription,
                created_at=created_at, prorate_to=prorate_to,
                cart_item=cart_item)
            # option is selected
            if len(options) == 1:
                # We only have one option.
                # It could happen when we use a 100% discount coupon
                # with advance discounts; in which case the advance
                # discounts would be cancelled. nothing is totally free.
                line = options[0]
                lines += [line]
                options = []
            elif (cart_item.option > 0 and
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

        return {
            'subscription': subscription,
            'name': cart_item.name,
            'lines': lines,
            'options': options,
            'descr': cart_item.descr,
        }


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
        invoicables = []
        for cart_item in CartItem.objects.get_cart(user=user):
            invoicables += [self.cart_item_as_invoicable(
                cart_item, customer, at_time=created_at)]
        return invoicables


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
            queryset = get_organization_model().objects.accessible_by(
                self.user).filter(is_active=True).exclude(
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


class OrganizationCreateMixin(object):

    user_model = get_user_model()

    def create_organization(self, validated_data):
        organization_model = get_organization_model()
        organization = organization_model(
            slug=validated_data.get('slug', None),
            full_name=validated_data.get('full_name'),
            email=validated_data.get('email'),
            default_timezone=validated_data.get(
                'default_timezone', settings.TIME_ZONE),
            phone=validated_data.get('phone', ""),
            street_address=validated_data.get('street_address', ""),
            locality=validated_data.get('locality', ""),
            region=validated_data.get('region', ""),
            postal_code=validated_data.get('postal_code', ""),
            country=validated_data.get('country', ""),
            extra=validated_data.get('extra'))
        organization.is_personal = (validated_data.get('type') == 'personal')
        with transaction.atomic():
            try:
                if organization.is_personal:
                    try:
                        user = self.user_model.objects.get(
                            username=organization.slug)
                        if not organization.full_name:
                            organization.full_name = user.get_full_name()
                        if not organization.email:
                            organization.email = user.email
                        # We are saving the `Organization` after the `User`
                        # exists in the database so we can retrieve
                        # the full_name and email from that attached user
                        # if case they were not provided in the API call.
                        organization.save()
                    except self.user_model.DoesNotExist:
                        #pylint:disable=unused-variable
                        # We are saving the `Organization` when the `User`
                        # does not exist so we have a chance to create
                        # a slug/username.
                        organization.save()
                        first_name, mid, last_name = full_name_natural_split(
                            organization.full_name)
                        user = self.user_model.objects.create_user(
                            username=organization.slug,
                            email=organization.email,
                            first_name=first_name,
                            last_name=last_name)
                    organization.add_manager(user)
                else:
                    # When `slug` is not present, `save` would try to create
                    # one from the `full_name`.
                    organization.save()
            except IntegrityError as err:
                handle_uniq_error(err)

        return organization


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
        # `get_organization_model().slug == User.username`.
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
            role__user__username=models.F('slug')).extra(select={
            'credentials': ("NOT (password LIKE '" + UNUSABLE_PASSWORD_PREFIX
            + "%%')")}).values_list('pk', 'credentials'))
        for profile in records:
            if profile.pk in personal:
                profile.is_personal = True
                profile.credentials = personal[profile.pk]
        return page


class ChargeMixin(OrganizationMixin):
    """
    Mixin for a ``Charge`` object that will first retrieve the state of
    the ``Charge`` from the processor API.

    This mixin is intended to be used for API requests. Pages should
    use the parent ChargeMixin and use AJAX calls to retrieve the state
    of a ``Charge`` in order to deal with latency and service errors
    from the processor.
    """
    model = Charge
    slug_field = 'processor_key'
    slug_url_kwarg = 'charge'

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.model.objects.filter(customer=self.organization)
        kwargs = {self.slug_field: self.kwargs.get(self.slug_url_kwarg)}
        charge = get_object_or_404(queryset, **kwargs)
        charge.retrieve()
        return charge


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


class InvoicablesMixin(OrganizationMixin):
    """
    Mixin a list of invoicables
    """
    @property
    def invoicables(self):
        if not hasattr(self, '_invoicables'):
            self._invoicables = self.as_invoicables(
                self.request.user, self.organization)
            self._invoicables.sort(
                key=lambda invoicable: str(invoicable['subscription']))
        return self._invoicables

    @property
    def invoicables_broker_fee_amount(self):
        if not hasattr(self, '_invoicables_broker_fee_amount'):
            self._invoicables_broker_fee_amount = 0
            for invoicable in self.invoicables:
                for invoiced_item in invoicable['lines']:
                    if invoiced_item.subscription:
                        self._invoicables_broker_fee_amount += \
                            invoiced_item.subscription.plan.prorate_transaction(
                                invoiced_item.dest_amount)
        return self._invoicables_broker_fee_amount

    @property
    def invoicables_provider(self):
        if not hasattr(self, '_invoicables_provider'):
            providers = set([])
            for invoicable in self.invoicables:
                providers |= set(Transaction.objects.providers(
                    invoicable['lines']))
            if len(providers) == 1:
                self._invoicables_provider = list(providers)[0]
            else:
                self._invoicables_provider = get_broker()
        return self._invoicables_provider

    @property
    def invoicables_lines_price(self):
        if not hasattr(self, '_invoicables_lines_price'):
            lines_amount = 0
            lines_unit = settings.DEFAULT_UNIT
            for invoicable in self.invoicables:
                if len(invoicable['options']) > 0:
                    # In case it is pure options, no lines.
                    lines_unit = invoicable['options'][0].dest_unit
                    invoicable['selected_option'] = 1
                    for rank, line in enumerate(invoicable['options']):
                        setattr(line, 'rank', rank + 1)
                for line in invoicable['lines']:
                    lines_amount += line.dest_amount
                    lines_unit = line.dest_unit
            current_plan = None
            for invoicable in self.invoicables:
                plan = invoicable['subscription'].plan
                if current_plan is None or plan != current_plan:
                    invoicable['is_changed'] = (current_plan is not None)
                    current_plan = plan
                    current_plan.is_removable = True
                for line in invoicable['lines']:
                    if line.pk:
                        current_plan.is_removable = False
            self._invoicables_lines_price = Price(lines_amount, lines_unit)
        return self._invoicables_lines_price

    def get_queryset(self):
        return self.invoicables

    def get_context_data(self, **kwargs):
        context = super(InvoicablesMixin, self).get_context_data(**kwargs)
        context.update(self.get_redirect_path())
        context.update({
            'invoicables': self.invoicables,
            'lines_price': self.invoicables_lines_price
        })
        return context

    def get_initial(self):
        kwargs = super(InvoicablesMixin, self).get_initial()
        for invoicable in self.invoicables:
            if invoicable['options']:
                kwargs.update({invoicable['name']: ""})
        return kwargs

    def get_redirect_path(self, **kwargs): #pylint: disable=unused-argument
        context = {}
        redirect_path = validate_redirect_url(
            self.request.GET.get(REDIRECT_FIELD_NAME, None))
        if redirect_path:
            context.update({REDIRECT_FIELD_NAME: redirect_path})
        return context


class BalanceAndCartMixin(BalanceDueMixin, CartMixin):

    def as_invoicables(self, user, customer, at_time=None):
        invoicables = BalanceDueMixin.as_invoicables(
            self, user, customer, at_time=at_time)
        invoicables += CartMixin.as_invoicables(
            self, user, customer, at_time=at_time)
        return invoicables


class ProviderMixin(OrganizationMixin):
    """
    Returns an ``Organization`` from a URL or the site owner by default.
    """

    def get_organization(self):
        if self.organization_url_kwarg in self.kwargs:
            queryset = get_organization_model().objects.filter(
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
    subscriber_url_kwarg = settings.PROFILE_URL_KWARG

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
        plan = self.kwargs.get('plan', self.kwargs.get('subscribed_plan', None))
        if plan:
            kwargs.update({'plan__slug': plan})
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
        obj = queryset.filter(
            ends_at__gt=datetime_or_now()).order_by('ends_at').first()
        if not obj:
            raise Http404(_("cannot find active subscription to"\
                " %(plan)s for %(organization)s") % {
                'plan': self.kwargs.get('plan', self.kwargs.get(
                    'subscribed_plan', None)),
                'organization': self.kwargs.get(self.subscriber_url_kwarg)})
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
    search_fields = (
        'user__username',
        'user__first_name',
        'user__last_name',
        'user__email'
    )
    ordering_fields = (
        ('slug', 'user__username'),
        ('plan', 'plan'),
        ('created_at', 'created_at')
    )
    ordering = ('created_at',)

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
        'last_name'
    )
    ordering_fields = (
        ('full_name', 'full_name'),
        ('created_at', 'created_at'),
    )

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
    ordering_fields = (
        ('organization__full_name', 'full_name'),
        ('user__username', 'username'),
        ('role_description__title', 'role_name'),
        ('grant_key', 'grant_key'),
        ('request_key', 'request_key'),
        ('created_at', 'created_at')
    )
    ordering = ('-created_at', 'user__username',)

    filter_backends = (SearchFilter, OrderingFilter)


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
    ordering_fields = (
        ('organization__full_name', 'organization'),
        ('plan__title', 'plan'),
        ('created_at', 'created_at'),
        ('ends_at', 'ends_at')
    )
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
    ordering_fields = (
        ('first_name', 'first_name'),
        ('last_name', 'last_name'),
        ('email', 'email'),
        ('date_joined', 'created_at')
    )
    ordering = ('first_name',)

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
            role_descr_slug = self.kwargs.get('role')
            if role_descr_slug:
                try:
                    self._role_description = \
                        self.organization.get_role_description(role_descr_slug)
                except RoleDescription.DoesNotExist:
                    raise Http404(
                        _("RoleDescription '%(role)s' does not exist.")
                        % {'role': role_descr_slug})
            else:
                self._role_description = None
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


def _as_html_description(transaction_descr,
                         orig_organization=None, dest_organization=None,
                         dest_account=None, active_links=True):
    #pylint:disable=too-many-locals
    result = transaction_descr
    for pat, trans in six.iteritems(humanize.REGEX_TO_TRANSLATION):
        look = re.match(pat, transaction_descr)
        if look:
            groups = {}
            for key in six.iterkeys(humanize.REGEXES):
                try:
                    groups.update({key: (int(look.group(key))
                        if key in ['nb_periods', 'quantity']
                        else look.group(key))})
                except IndexError:
                    pass

            charge = groups.get('charge')
            if (charge and
                dest_organization and dest_account and orig_organization):
                if active_links:
                    groups.update({'charge':
                        '<a href="%s">%s</a>' % (reverse('saas_charge_receipt',
                        args=(dest_organization
                        if dest_account == Transaction.EXPENSES
                        else orig_organization, look.group('charge'),)),
                        charge)})

            period_name = groups.get('period_name')
            nb_periods = groups.get('nb_periods')
            if nb_periods and period_name:
                groups.update({'period_name': humanize.translate_period_name(
                    period_name, nb_periods)})

            subscriber = groups.get('subscriber')
            if (subscriber and
                orig_organization and dest_organization):
                if str(orig_organization) == subscriber:
                    provider = dest_organization
                else:
                    provider = orig_organization
                if active_links:
                    groups.update({'subscriber': '<a href="%s">%s</a>' % (
                        reverse('saas_organization_profile',
                        args=(subscriber,)), subscriber)})
            else:
                provider = orig_organization
                subscriber = dest_organization

            plan = groups.get('plan')
            if (plan and
                provider and subscriber):
                try:
                    plan_title = Plan.objects.get(slug=plan).title
                except Plan.DoesNotExist:
                    plan_title = plan
                if active_links:
                    groups.update({'plan':
                        ('<a href="%s%s/">%s</a>' % (
                        product_url(provider, subscriber),
                        plan, plan_title))})
                else:
                    groups.update({'plan': plan_title})

            descr = groups.get('descr')
            if descr:
                groups.update({'descr': _as_html_description(descr)})

            result = trans % groups
            pos = transaction_descr.rfind(' - ')
            if pos > 0:
                result += humanize.translate_descr_suffix(
                    transaction_descr[pos + 3:])
            break
    return result


def as_html_description(transaction_model, active_links=True):
    """
    Add hyperlinks into a transaction description.
    """
    return _as_html_description(
        transaction_model.descr,
        transaction_model.orig_organization,
        transaction_model.dest_organization,
        transaction_model.dest_account,
        active_links=active_links)


def get_charge_context(charge):
    """
    Return a dictionnary useful to populate charge receipt templates.
    """
    context = {
        'last4': charge.get_last4_display(),
        'exp_date': charge.exp_date,
        'charge': charge,
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
    if not is_broker(provider):
        location = '/%s' % provider + location
    return location
