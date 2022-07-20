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
"""
Profiles appear at 3 level of details: slug, OrganizationSerializer and
OrganizationDetailSerializer. The slug representation is used when
a unique identifier for the profile is required but otherwise dealing with
profiles is not the main purpose of the API call. The OrganizationSerializer
is used when minimal information about the profile should be returned
(slug, full_name, picture) for display but otherwise access to personal
information (street_address, etc.) have not been granted to the requesting user.
The OrganizationDetailSerializer is used when the requesting user has been
granted access to personal information.
"""
from __future__ import unicode_literals

import logging

from django.core import validators
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import is_password_usable
from django.db import transaction
from django.template.defaultfilters import slugify
from django_countries.serializer_fields import CountryField
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
import phonenumbers

from .. import settings
from ..compat import gettext_lazy as _, reverse, six
from ..decorators import _valid_manager
from ..humanize import as_money
from ..mixins import as_html_description, product_url
from ..models import (AdvanceDiscount, BalanceLine, CartItem, Charge, Coupon,
    Plan, RoleDescription, Subscription, Transaction, get_broker)
from ..utils import (build_absolute_uri, get_organization_model, get_role_model,
    get_user_serializer)

#pylint: disable=no-init

LOGGER = logging.getLogger(__name__)


class EnumField(serializers.Field):
    """
    Treat a ``PositiveSmallIntegerField`` as an enum.
    """
    choices = {}
    inverted_choices = {}

    def __init__(self, choices, *args, **kwargs):
        self.choices = dict(choices)
        self.inverted_choices = {
            slugify(val): key for key, val in six.iteritems(self.choices)}
        super(EnumField, self).__init__(*args, **kwargs)

    def to_representation(self, value):
        if isinstance(value, list):
            result = [slugify(self.choices.get(item, None))
                for item in value]
        else:
            result = slugify(self.choices.get(value, None))
        return result

    def to_internal_value(self, data):
        if isinstance(data, list):
            result = [self.inverted_choices.get(item, None) for item in data]
        else:
            result = self.inverted_choices.get(data, None)
        if result is None:
            if not data:
                raise ValidationError(_("This field cannot be blank."))
            raise ValidationError(_("'%(data)s' is not a valid choice."\
                " Expected one of %(choices)s.") % {
                    'data': data, 'choices': [str(choice)
                    for choice in six.iterkeys(self.inverted_choices)]})
        return result


class PhoneField(serializers.Field):

    def to_representation(self, value):
        return str(value)

    def to_internal_value(self, data):
        """
        Returns a formatted phone number as a string.
        """
        try:
            phone_number = phonenumbers.parse(data, None)
        except phonenumbers.NumberParseException as err:
            LOGGER.info("tel %s:%s", data, err)
            phone_number = None
        if not phone_number:
            try:
                phone_number = phonenumbers.parse(data, "US")
            except phonenumbers.NumberParseException:
                LOGGER.info("tel %s:%s", data, err)
                phone_number = None

        if not phone_number:
            if self.required:
                raise ValidationError(self.error_messages['required'])
            return None

        if not phonenumbers.is_valid_number(phone_number):
            raise ValidationError(self.error_messages['invalid'])
        return phonenumbers.format_number(
            phone_number, phonenumbers.PhoneNumberFormat.E164)


class PlanRelatedField(serializers.RelatedField):

    def __init__(self, **kwargs):
        super(PlanRelatedField, self).__init__(
            queryset=Plan.objects.all(), **kwargs)

    def to_representation(self, value):
        return value.slug

    def to_internal_value(self, data):
        return get_object_or_404(Plan.objects.all(), slug=data)


class RoleDescriptionRelatedField(serializers.RelatedField):

    def __init__(self, **kwargs):
        super(RoleDescriptionRelatedField, self).__init__(
            queryset=RoleDescription.objects.all(), **kwargs)

    def to_representation(self, value):
        return value.slug

    def to_internal_value(self, data):
        return get_object_or_404(RoleDescription.objects.all(), slug=data)


class NoModelSerializer(serializers.Serializer):

    def create(self, validated_data):
        raise RuntimeError('`create()` should not be called.')

    def update(self, instance, validated_data):
        raise RuntimeError('`update()` should not be called.')


class PriceSerializer(NoModelSerializer):

    amount = serializers.IntegerField(
        help_text=_("amount in unit"))
    unit = serializers.CharField(
        help_text=_("Three-letter ISO 4217 code for currency unit (ex: usd)"))


class BalanceLineSerializer(serializers.ModelSerializer):

    class Meta:
        model = BalanceLine
        fields = ('title', 'selector', 'rank')
        extra_kwargs = {'selector': {'required': False}}


class UpdateRankSerializer(NoModelSerializer):

    oldpos = serializers.IntegerField(
        help_text=_("old rank for a line in the list of lines"))
    newpos = serializers.IntegerField(
        help_text=_("new rank for the line in the list of lines"))


class BankSerializer(NoModelSerializer):
    """
    Information to verify a deposit account
    """
    bank_name = serializers.CharField(
        help_text=_("Name of the deposit account"))
    last4 = serializers.CharField(
        help_text=_("Last 4 characters of the deposit account identifier"))
    balance_amount = serializers.IntegerField(
        help_text=_("Amount available to transfer to the provider"\
            " deposit account"))
    balance_unit = serializers.CharField(
        help_text=_("Three-letter ISO 4217 code for currency unit (ex: usd)"))


class ProcessorAuthSerializer(NoModelSerializer):

    STRIPE_PUB_KEY = serializers.CharField(required=False,
        help_text=_("Processor public key (Stripe)"))
    STRIPE_INTENT_SECRET = serializers.CharField(required=False,
        help_text=_("PaymentIntent or SetupIntent secret for SCA (Stripe)"))
    STRIPE_ACCOUNT = serializers.CharField(required=False,
        help_text=_("Connected account identifier (Stripe)"))


class CardSerializer(NoModelSerializer):
    """
    Information to verify a credit card
    """
    processor = ProcessorAuthSerializer(required=False,
      help_text=_("Keys to authenticate the client with the payment processor"))
    last4 = serializers.CharField(
        help_text=_("Last 4 digits of the credit card on file"))
    exp_date = serializers.CharField(
        help_text=_("Expiration date of the credit card on file"))


class CardTokenSerializer(NoModelSerializer):
    """
    Updates a payment method on file.
    """
    token = serializers.CharField(
        help_text=_("Processor token to retrieve the payment method"))
    full_name = serializers.CharField(required=False,
        help_text=_("Full name"))
    email = serializers.EmailField(required=False,
        help_text=_("E-mail address for the account"))
    phone = serializers.CharField(required=False, allow_blank=True,
        help_text=_("Phone number"))
    street_address = serializers.CharField(required=False, allow_blank=True,
        help_text=_("Street address"))
    locality = serializers.CharField(required=False, allow_blank=True,
        help_text=_("City/Town"))
    region = serializers.CharField(required=False, allow_blank=True,
        help_text=_("State/Province/County"))
    postal_code = serializers.CharField(required=False, allow_blank=True,
        help_text=_("Zip/Postal code"))
    country = CountryField(required=False, allow_blank=True,
        help_text=_("Country"))


class ChargeSerializer(serializers.ModelSerializer):

    state = serializers.CharField(source='get_state_display',
        help_text=_("Current state (i.e. created, done, failed, disputed)"))
    readable_amount = serializers.SerializerMethodField(
        help_text=_("Amount and unit in a commonly accepted readable format"))
    detail = serializers.CharField(read_only=True, required=False,
        help_text=_("Feedback for the user in plain text"))
    last4 = serializers.CharField(source='get_last4_display', read_only=True,
        help_text=_("Last 4 digits of the credit card used"))

    @staticmethod
    def get_readable_amount(charge):
        return as_money(charge.amount, charge.unit)

    class Meta:
        model = Charge
        fields = ('created_at', 'amount', 'unit', 'readable_amount',
            'description', 'last4', 'exp_date', 'processor_key', 'state',
            'detail')
        read_only_fields = ('created_at', 'amount', 'unit', 'readable_amount',
            'description', 'last4', 'exp_date', 'processor_key', 'state',
            'detail')


class CouponSerializer(serializers.ModelSerializer):
    """
    Serializer to retrieve or update a `Coupon`.
    """
    code = serializers.CharField(required=False,
        help_text=_("Unique identifier per provider, typically used in URLs"))
    discount_type = EnumField(choices=Coupon.DISCOUNT_CHOICES,
        help_text=_("Type of discount ('percentage', 'currency', or 'period')"))
    plan = PlanRelatedField(required=False, allow_null=True,
        help_text=_("Coupon will only apply to this plan"))

    class Meta:
        model = Coupon
        fields = ('code', 'discount_type', 'discount_value',
            'created_at', 'ends_at', 'description',
            'nb_attempts', 'plan')


class CouponCreateSerializer(CouponSerializer):
    """
    Serializer to create a coupon, including the `code`.
    """
    code = serializers.CharField(required=True,
        help_text=_("Unique identifier per provider, typically used in URLs"))
    discount_type = EnumField(required=True, choices=Coupon.DISCOUNT_CHOICES,
        help_text=_("Type of discount ('percentage', 'currency', or 'period')"))
    discount_value = serializers.IntegerField(required=True,
        help_text=_("Amount of the discount"))

    @staticmethod
    def validate_plan(plan):
        if plan and not plan.is_active:
            raise ValidationError(_("The plan is inactive. "\
                "As a result the coupon will have no effect."))
        return plan

    class Meta(CouponSerializer.Meta):
        model = CouponSerializer.Meta.model
        fields = CouponSerializer.Meta.fields


class EmailChargeReceiptSerializer(NoModelSerializer):
    """
    Response for the API call to send an e-mail duplicate to the customer.
    """
    charge_id = serializers.CharField(read_only=True,
        help_text=_("Charge identifier (i.e. matches the URL {charge}"\
            " parameter)"))
    email = serializers.EmailField(read_only=True,
        help_text=_("E-mail address to which the receipt was sent."))
    detail = serializers.CharField(read_only=True,
        help_text=_("Feedback for the user in plain text"))


class ForceSerializer(NoModelSerializer):

    force = serializers.BooleanField(required=False,
        help_text=_("Forces invite of user/organization that could"\
        " not be found"))


class DatetimeValueTuple(serializers.ListField):

    child = serializers.CharField() # XXX (Datetime, Integer)
    min_length = 2
    max_length = 2


class TableSerializer(NoModelSerializer):

    # XXX use `key` instead of `slug` here?
    key = serializers.CharField(
        help_text=_("Unique key in the table for the data series"))
    selector = serializers.CharField(
        required=False, # XXX only in balances.py
        help_text=_("Filter on transaction accounts"))
    values = serializers.ListField(
        child=DatetimeValueTuple(),
        help_text=_("List of (datetime, integer) couples that represents"\
        " the data serie"))


class MetricsSerializer(NoModelSerializer):

    scale = serializers.FloatField(required=False,
        help_text=_("The scale of the number reported in the tables (ex: 1000"\
        " when numbers are reported in thousands of dollars)"))
    unit = serializers.CharField(required=False,
        help_text=_("Three-letter ISO 4217 code for currency unit (ex: usd)"))
    title = serializers.CharField(
        help_text=_("Title for the table"))
    table = TableSerializer(many=True,
        help_text=_("Data series"))


class RefundChargeItemSerializer(NoModelSerializer):
    """
    One item to refund on a `Charge`.
    """
    num = serializers.IntegerField(
        help_text=_("Line item index counting from zero."))
    refunded_amount = serializers.IntegerField(required=False,
        help_text=_("The amount to refund cannot be higher than the amount"\
        " of the line item minus the total amount already refunded on that"\
        " line item."))


class RefundChargeSerializer(NoModelSerializer):
    """
    Response for the API call to send an e-mail duplicate to the customer.
    """
    lines = RefundChargeItemSerializer(many=True,
        help_text=_("Line items in a charge to be refunded"))


class OrganizationBalanceSerializer(NoModelSerializer):

    balance_amount = serializers.IntegerField(read_only=True,
      help_text=_("balance of all transactions in cents (i.e. 100ths) of unit"))
    balance_unit = serializers.CharField(read_only=True,
        help_text=_("three-letter ISO 4217 code for currency unit (ex: usd)"))

    class Meta:
        fields = ('balance_amount', 'balance_unit')


class WithEndsAtByPlanSerializer(NoModelSerializer):

    plan = serializers.SlugField(source='plan__slug', read_only=True)
    ends_at = serializers.DateTimeField(source='ends_at__max', read_only=True)

    class Meta:
        fields = ('plan', 'ends_at')


class WithSubscriptionSerializer(serializers.ModelSerializer):

    plan = serializers.SlugRelatedField(read_only=True, slug_field='slug')

    class Meta:
        model = Subscription
        fields = ('created_at', 'ends_at', 'plan', 'auto_renew')


class OrganizationSerializer(serializers.ModelSerializer):

    # If we put ``slug`` in the ``read_only_fields``, it will be set ``None``
    # when one creates an opt-in subscription.
    # If we don't define ``slug`` here, the serializer validators will raise
    # an exception "Organization already exists in database".
    slug = serializers.SlugField(read_only=True,
        help_text=_("Unique identifier shown in the URL bar"))
    printable_name = serializers.SerializerMethodField(read_only=True,
        help_text=_("Name that can be safely used for display in HTML pages"))
    credentials = serializers.SerializerMethodField(read_only=True,
        help_text=_("True if the account has valid login credentials"))

    class Meta:
        model = get_organization_model()
        fields = ('slug', 'printable_name', 'picture', 'type', 'credentials')
        read_only_fields = ('printable_name', 'type', 'credentials')

    @staticmethod
    def get_printable_name(obj):
        return obj.printable_name

    @staticmethod
    def get_credentials(obj):
        if hasattr(obj, 'credentials'):
            return bool(obj.credentials)
        if hasattr(obj, 'user'):
            return is_password_usable(obj.user.password)
        return False

    @staticmethod
    def get_type(obj):
        if not obj.pk:
            return 'user'
        if hasattr(obj, 'is_personal') and obj.is_personal:
            return 'personal'
        return 'organization'

OrganizationSerializer._declared_fields["type"] = \
    serializers.SerializerMethodField(#pylint:disable=protected-access
    help_text=_("One of 'organization', 'personal' or 'user'"))


class OrganizationDetailSerializer(OrganizationSerializer):

    slug = serializers.SlugField(required=False,
        help_text=_("Unique identifier shown in the URL bar"))
    full_name = serializers.CharField(help_text=_("Full name"))
    default_timezone = serializers.CharField(required=False,
        help_text=_("Timezone to use when reporting metrics"))
    email = serializers.EmailField(required=False,
        help_text=_("E-mail address"))
    phone = serializers.CharField(required=False, allow_blank=True,
        help_text=_("Phone number"))
    street_address = serializers.CharField(required=False, allow_blank=True,
        help_text=_("Street address"))
    locality = serializers.CharField(required=False, allow_blank=True,
        help_text=_("City/Town"))
    region = serializers.CharField(required=False, allow_blank=True,
        help_text=_("State/Province/County"))
    postal_code = serializers.CharField(required=False, allow_blank=True,
        help_text=_("Zip/Postal code"))
    country = CountryField(required=False, allow_blank=True,
        help_text=_("Country"))
    is_bulk_buyer = serializers.BooleanField(required=False, default=False,
        help_text=_("Enable GroupBuy"))
    extra = serializers.CharField(required=False, allow_null=True,
        help_text=_("Extra meta data (can be stringify JSON)"))

    detail = serializers.CharField(read_only=True, required=False,
        help_text=_("Describes the result of the action"\
            " in human-readable form"))

    class Meta(OrganizationSerializer.Meta):
        fields = OrganizationSerializer.Meta.fields + (
            'full_name', 'created_at', 'email', 'phone',
            'street_address', 'locality', 'region', 'postal_code', 'country',
            'default_timezone', 'is_provider', 'is_bulk_buyer', 'extra',
            'detail')
        read_only_fields = ('created_at', 'detail')


class OrganizationCreateSerializer(OrganizationDetailSerializer):
    # We have a special serializer for Create (i.e. POST request)
    # because we want to include the `type` field.

    @staticmethod
    def validate_type(value):
        if value not in ('personal', 'organization'):
            raise ValidationError(
                _("type must be one of 'personal' or 'organization'."))
        return value

    class Meta(OrganizationDetailSerializer.Meta):
        fields = OrganizationDetailSerializer.Meta.fields

OrganizationCreateSerializer._declared_fields["type"] = \
    serializers.CharField(required=False,#pylint:disable=protected-access
        help_text=_("One of 'organization', 'personal' or 'user'"))


class OrganizationWithSubscriptionsSerializer(OrganizationDetailSerializer):
    """
    Operational information on an Organization,
    bundled with its subscriptions.
    """
    subscriptions = WithSubscriptionSerializer(many=True, read_only=True)

    class Meta(OrganizationDetailSerializer.Meta):
        fields = OrganizationDetailSerializer.Meta.fields + (
            'subscriptions',)
        read_only_fields = OrganizationDetailSerializer.Meta.read_only_fields\
            + ('subscriptions',)


class OrganizationWithEndsAtByPlanSerializer(OrganizationSerializer):
    """
    Operational information on an Organization,
    bundled with its active subscriptions.
    """
    subscriptions = WithEndsAtByPlanSerializer(
        source='get_ends_at_by_plan', many=True, read_only=True)

    class Meta(OrganizationSerializer.Meta):
        fields = OrganizationSerializer.Meta.fields + (
            'email', 'subscriptions',)
        read_only_fields = OrganizationSerializer.Meta.read_only_fields\
            + ('subscriptions',)


class AdvanceDiscountSerializer(serializers.ModelSerializer):

    discount_type = EnumField(choices=AdvanceDiscount.DISCOUNT_CHOICES,
        help_text=_("Type of discount (periods, percentage or currency unit)"))

    class Meta:
        model = AdvanceDiscount
        fields = ('discount_type', 'discount_value', 'length')


class PlanSerializer(serializers.ModelSerializer):

    slug = serializers.SlugField(required=False,
        help_text=_("Unique identifier shown in the URL bar"))
    title = serializers.CharField(required=False,
        help_text=_("Title for the plan"))

    class Meta:
        model = Plan
        fields = ('slug', 'title',)


class PlanDetailSerializer(PlanSerializer):

    description = serializers.CharField(required=False,
        help_text=_("Free-form text description for the %(object)s") % {
            'object': 'plan'})
    is_active = serializers.BooleanField(required=False,
        help_text=_("True when customers can subscribe to the plan"))
    setup_amount = serializers.IntegerField(required=False,
        help_text=_("One-time amount to pay when the subscription starts"))
    period_amount = serializers.IntegerField(required=False,
        help_text=_("Amount billed every period"))
    period_type = EnumField(choices=Plan.INTERVAL_CHOICES, required=False,
        help_text=_("Natural period length of a subscription to the plan"\
        " (hourly, daily, weekly, monthly, yearly)"))
    renewal_type = EnumField(choices=Plan.RENEWAL_CHOICES, required=False,
        help_text=_("What happens at the end of a subscription period"\
        " (one-time, auto-renew, repeat)"))
    app_url = serializers.SerializerMethodField(
      help_text=_("URL to the homepage for the profile associated to the plan"))
    organization = OrganizationSerializer(read_only=True,
        help_text=_("Provider of the plan"))
    skip_optin_on_grant = serializers.BooleanField(required=False,
        help_text=_("True when a subscriber can automatically be subscribed"\
        " to the plan by its provider. Otherwise the subscriber must manually"\
        " accept the subscription. (defaults to False)"))
    optin_on_request = serializers.BooleanField(required=False,
        help_text=_("True when a provider must manually accept a subscription"\
        " to the plan initiated by a subscriber. (defaults to False)"))
    advance_discounts = AdvanceDiscountSerializer(many=True, required=False,
        help_text=_("Discounts when periods are paid in advance."))

    discounted_period_amount = serializers.SerializerMethodField(required=False,
        help_text=_("Discounted amount for the first period"))
    is_cart_item = serializers.SerializerMethodField(required=False,
        help_text=_("The plan is part of the cart to checkout"))

    detail = serializers.CharField(read_only=True, required=False,
        help_text=_("Describes the result of the action"\
            " in human-readable form"))

    class Meta:
        model = PlanSerializer.Meta.model
        fields = PlanSerializer.Meta.fields + ('description', 'is_active',
            'setup_amount', 'period_amount', 'period_type', 'app_url',
            'advance_discounts', 'unit', 'organization', 'extra',
            'period_length', 'renewal_type', 'is_not_priced',
            'created_at', 'skip_optin_on_grant', 'optin_on_request',
            'discounted_period_amount', 'is_cart_item', 'detail')
        read_only_fields = ('app_url',
            'discounted_period_amount', 'is_cart_item', 'detail')

    @staticmethod
    def get_discounted_period_amount(obj):
        return getattr(obj, 'discounted_period_amount', obj.period_amount)

    @staticmethod
    def get_is_cart_item(obj):
        return getattr(obj, 'is_cart_item', False)

    @staticmethod
    def get_app_url(obj):
        return product_url(obj.organization)

    def create(self, validated_data):
        advance_discounts = validated_data.pop('advance_discounts', [])
        with transaction.atomic():
            instance = Plan.objects.create(**validated_data)
            for advance_discount in advance_discounts:
                AdvanceDiscount.objects.create(
                    plan=instance,
                    discount_type=advance_discount.get('discount_type'),
                    discount_value=advance_discount.get('discount_value'),
                    length=advance_discount.get('length'))

        return instance

    def update(self, instance, validated_data):
        advance_discounts = validated_data.pop('advance_discounts', [])
        for attr, value in six.iteritems(validated_data):
            setattr(instance, attr, value)

        with transaction.atomic():
            instance.save()
            instance.advance_discounts.all().delete()
            for advance_discount in advance_discounts:
                AdvanceDiscount.objects.create(
                    plan=instance,
                    discount_type=advance_discount.get('discount_type'),
                    discount_value=advance_discount.get('discount_value'),
                    length=advance_discount.get('length'))

        return instance


class PlanCreateSerializer(PlanDetailSerializer):
    """
    Serializer to create plans in POST requests
    """
    title = serializers.CharField(required=True,
        help_text=_("Title for the plan"))

    class Meta(PlanDetailSerializer.Meta):
        fields = PlanDetailSerializer.Meta.fields


class OrganizationInviteSerializer(OrganizationCreateSerializer):

    def validate(self, attrs):
        # XXX This is because we use `OrganizationInviteSerializer`
        # in `ProvidedSubscriptionCreateSerializer`.
        if not (attrs.get('slug') or (attrs.get('full_name') and
                attrs.get('email') and attrs.get('type'))):
            raise ValidationError(_("One of slug or (full_name, email,"\
                " type) should be present"))
        return super(OrganizationInviteSerializer, self).validate(attrs)

    class Meta(OrganizationCreateSerializer.Meta):
        fields = OrganizationCreateSerializer.Meta.fields


class SubscriptionSerializer(serializers.ModelSerializer):

    organization = OrganizationDetailSerializer(read_only=True,
        help_text=_("Profile subscribed to the plan"))
    plan = PlanSerializer(read_only=True,
        help_text=_("Plan the profile is subscribed to"))
    editable = serializers.SerializerMethodField(
        help_text=_("True if the request user is able to update"\
        " the subscription. Typically a manager for the plan provider."))

    class Meta:
        model = Subscription
        fields = ('created_at', 'ends_at', 'description',
                  'organization', 'plan', 'auto_renew',
                  'editable', 'extra', 'grant_key', 'request_key')
        # XXX grant_key and request_key should probably be removed.
        read_only_fields = ('grant_key', 'request_key')

    def get_editable(self, subscription):
        return bool(_valid_manager(self.context['request'],
            [subscription.plan.organization]))


class SubscribedSubscriptionSerializer(SubscriptionSerializer):

    remove_api_url = serializers.SerializerMethodField(
        help_text=_("URL API endpoint to remove the subscription"\
        " grant or request"))

    class Meta(SubscriptionSerializer.Meta):
        fields = SubscriptionSerializer.Meta.fields + (
            'remove_api_url',)

    def get_remove_api_url(self, obj):
        return build_absolute_uri(self.context['request'], location=reverse(
            'saas_api_subscription_detail', args=(
                obj.organization, obj.plan,)))


class ProvidedSubscriptionSerializer(SubscriptionSerializer):

    accept_request_api_url = serializers.SerializerMethodField(
        help_text=_("URL API endpoint to grant the subscription"))
    remove_api_url = serializers.SerializerMethodField(
        help_text=_("URL API endpoint to remove the subscription"\
        " grant or request"))

    class Meta(SubscriptionSerializer.Meta):
        fields = SubscriptionSerializer.Meta.fields + (
            'accept_request_api_url', 'remove_api_url')

    def get_accept_request_api_url(self, obj):
        if obj.request_key:
            return build_absolute_uri(self.context['request'], location=reverse(
                'saas_api_subscription_grant_accept', args=(
                obj.plan.organization, obj.request_key)))
        return None

    def get_remove_api_url(self, obj):
        return build_absolute_uri(self.context['request'], location=reverse(
            'saas_api_plan_subscription', args=(
                obj.plan.organization, obj.plan, obj.organization)))


class ProvidedSubscriptionCreateSerializer(serializers.ModelSerializer):

    organization = OrganizationInviteSerializer(
        help_text=_("Profile subscribed to the plan"))
    message = serializers.CharField(required=False, allow_null=True,
        help_text=_("Message to send along the invitation"))

    class Meta:
        model = Subscription
        fields = ('organization', 'message')


class TransactionSerializer(serializers.ModelSerializer):
    """
    A `Transaction` in the double-entry bookkeeping ledger.
    """

    orig_organization = serializers.SlugRelatedField(
        read_only=True, slug_field='slug',
        help_text=_("Billing profile from which funds are withdrawn"))
    dest_organization = serializers.SlugRelatedField(
        read_only=True, slug_field='slug',
        help_text=_("Billing profile to which funds are deposited"))
    description = serializers.CharField(source='descr', read_only=True,
        help_text=_("Free-form text description for the %(object)s") % {
            'object': 'transaction'})
    amount = serializers.CharField(source='dest_amount', read_only=True,
        help_text=_("Amount being transfered"))
    is_debit = serializers.CharField(source='dest_amount', read_only=True,
        help_text=_("True if the transaction is indentified as a debit in"\
        " the API context"))

    def _is_debit(self, value):
        """
        True if the transaction can be tagged as a debit. That is
        it is either payable by the organization or the transaction
        moves from a Funds account to the organization's Expenses account.
        """
        #pylint: disable=no-member
        if ('view' in self.context
            and hasattr(self.context['view'], 'organization')):
            return value.is_debit(self.context['view'].organization)
        return False

    def to_representation(self, instance):
        ret = super(TransactionSerializer, self).to_representation(instance)
        is_debit = self._is_debit(instance)
        if is_debit:
            amount = as_money(instance.orig_amount, '-%s' % instance.orig_unit)
        else:
            amount = as_money(instance.dest_amount, instance.dest_unit)
        ret.update({
            'description': as_html_description(instance),
            'is_debit': is_debit,
            'amount': amount})
        return ret

    class Meta:
        model = Transaction
        fields = ('created_at', 'description', 'amount', 'is_debit',
            'orig_account', 'orig_organization', 'orig_amount', 'orig_unit',
            'dest_account', 'dest_organization', 'dest_amount', 'dest_unit')


class ChargeItemSerializer(NoModelSerializer):

    invoiced = TransactionSerializer()
    refunded = TransactionSerializer(many=True)


class CreateOfflineTransactionSerializer(NoModelSerializer):
    """
    Serializer to validate the input that creates an off-line transaction.
    """
    subscription = serializers.CharField(
        help_text="The subscription the offline transaction refers to.")
    created_at = serializers.DateTimeField(
        help_text=_("Date/time of creation (in ISO format)"))
    # XXX Shouldn't this be same format as TransactionSerializer.amount?
    amount = serializers.DecimalField(None, 2)
    descr = serializers.CharField(required=False,
        help_text=_("Free-form text description for the %(object)s") % {
            'object': 'transaction'})


class OfflineTransactionSerializer(NoModelSerializer):
    """
    Serializer to format the output of importing an off-line transaction.
    """
    detail = serializers.CharField(required=False,
        help_text=_("Describes the result of the action"\
        " in human-readable form"))
    results = TransactionSerializer(many=True,
        help_text=_("transactions being created by the import"))


class CartItemSerializer(serializers.ModelSerializer):
    """
    serializer for a ``CartItem`` object.

    This serializer is typically used in coupon performance metrics.
    """
    user = get_user_serializer()(
        help_text=_("User the cart belongs to"))
    plan = PlanSerializer(
        help_text=_("Item in the cart (if plan)"))
    detail = serializers.SerializerMethodField(read_only=True, required=False,
        help_text=_("Describes the result of the action"\
            " in human-readable form"))

    class Meta:
        model = CartItem
        fields = ('created_at', 'user', 'plan', 'option', 'full_name',
            'sync_on', 'email', 'detail')
        read_only_fields = ('created_at', 'user', 'detail')

    @staticmethod
    def get_detail(obj):
        if hasattr(obj, 'detail'):
            return obj.detail
        if isinstance(obj, dict):
            return obj.get('detail')
        return None


class CartItemCreateSerializer(serializers.ModelSerializer):
    """
    Serializer to build a request.user set of plans to subscribe to (i.e. cart).
    """
    plan = PlanRelatedField(read_only=False, required=True,
        help_text=_("The plan to add into the request.user cart."))

    class Meta:
        model = CartItem
        fields = ('created_at', 'plan', 'option', 'full_name',
            'sync_on', 'email')
        read_only_fields = ('created_at',)


class CartItemUploadSerializer(NoModelSerializer):

    created = CartItemSerializer(many=True)
    updated = CartItemSerializer(many=True)
    failed = CartItemSerializer(many=True)


class InvoicableSerializer(NoModelSerializer):
    """
    serializer for an invoicable item with available options.
    """
    subscription = SubscriptionSerializer(read_only=True, help_text=_(
        "Subscription lines and options refer to."))
    lines = TransactionSerializer(many=True, help_text=_(
        "Line items to charge on checkout."))
    options = TransactionSerializer(read_only=True, many=True, help_text=(
        "Options to replace line items."))


class RoleDescriptionSerializer(serializers.ModelSerializer):

    organization = OrganizationSerializer(read_only=True,
        help_text=_("Profile the role type belongs to"))
    is_global = serializers.BooleanField(required=False,
        help_text=_("True when the role type is available for all profiles"))

    class Meta:
        model = RoleDescription
        fields = ('created_at', 'slug', 'title',
                  'skip_optin_on_grant', 'implicit_create_on_none',
                  'is_global', 'organization', 'extra')
        read_only_fields = ('created_at', 'slug', 'is_global')


class AccessibleSerializer(serializers.ModelSerializer):
    """
    Formats an entry in a list of ``Organization`` accessible by a ``User``.
    """
    organization = OrganizationSerializer(read_only=True,
        help_text=_("Profile the user has a role on"))
    role_description = RoleDescriptionSerializer(read_only=True,
        help_text=_("Description of the role"))
    accept_grant_api_url = serializers.SerializerMethodField(
        help_text=_("URL API endpoint to grant the role"))
    remove_api_url = serializers.SerializerMethodField(
        help_text=_("URL API endpoint to remove the role grant or request"))
    home_url = serializers.SerializerMethodField(
      help_text=_("URL to the homepage for the profile associated to the role"))
    settings_url = serializers.SerializerMethodField(
        help_text=_("URL to the settings page for the profile associated"\
        " to the role"))

    class Meta:
        model = get_role_model()
        fields = ('created_at', 'request_key',
            'organization', 'role_description',
            'home_url', 'settings_url',
            'accept_grant_api_url', 'remove_api_url')
        read_only_fields = ('created_at', 'request_key')

    def get_accept_grant_api_url(self, obj):
        if obj.grant_key:
            return build_absolute_uri(self.context['request'], location=reverse(
                'saas_api_accessibles_accept', args=(obj.user, obj.grant_key)))
        return None

    def get_remove_api_url(self, obj):
        role_description = (obj.role_description
            if obj.role_description else settings.MANAGER)
        return build_absolute_uri(self.context['request'], location=reverse(
            'saas_api_accessible_detail', args=(
                obj.user, role_description, obj.organization)))

    def get_settings_url(self, obj):
        req = self.context['request']
        org = obj.organization
        if org.is_provider:
            settings_location = build_absolute_uri(req, location=reverse(
                'saas_dashboard', args=(org.slug,)))
        else:
            settings_location = build_absolute_uri(req, location=reverse(
                'saas_organization_profile', args=(org.slug,)))
        return settings_location

    def get_home_url(self, obj):
        return product_url(get_broker(), subscriber=obj.organization,
            request=self.context['request'])


class AccessibleCreateSerializer(NoModelSerializer):
    """
    Invite a previously existing or new Organization
    """
    slug = serializers.SlugField(required=False, validators=[
        validators.RegexValidator(settings.ACCT_REGEX,
            _("Enter a valid organization slug."), 'invalid')],
        help_text=_("Profile to grant {user} a role onto"))
    email = serializers.EmailField(required=False,
        help_text=_("E-mail of profile to grant {user} a role onto"\
            " (potentially generating an invite to the site)"))
    message = serializers.CharField(max_length=255, required=False,
        help_text=_("Message to send along the invitation"))


class RoleSerializer(serializers.ModelSerializer):

    user = get_user_serializer()(read_only=True,
        help_text=_("User with the role"))
    organization = OrganizationDetailSerializer(read_only=True,
        help_text=_("Profile the user has a role on"))
    role_description = RoleDescriptionSerializer(read_only=True,
        help_text=_("Description of the role"))
    accept_request_api_url = serializers.SerializerMethodField(
        help_text=_("URL API endpoint to grant the role"))
    remove_api_url = serializers.SerializerMethodField(
        help_text=_("URL API endpoint to remove the role grant or request"))
    detail = serializers.CharField(read_only=True, required=False,
        help_text=_("Describes the result of the action"\
            " in human-readable form"))

    class Meta:
        model = get_role_model()
        fields = ('created_at', 'user', 'grant_key',
            'organization', 'role_description', 'accept_request_api_url',
            'remove_api_url', 'detail')
        read_only_fields = ('created_at', 'grant_key', 'role_description',
            'detail')

    def get_accept_request_api_url(self, obj):
        if obj.request_key:
            return build_absolute_uri(self.context['request'], location=reverse(
                'saas_api_roles_by_descr', args=(
                    obj.organization, obj.role_description)))
        return None

    def get_remove_api_url(self, obj):
        role_description = (obj.role_description
            if obj.role_description else settings.MANAGER)
        return build_absolute_uri(self.context['request'], location=reverse(
            'saas_api_role_detail', args=(
                obj.organization, role_description, obj.user)))


class RoleCreateSerializer(NoModelSerializer):
    """
    Invite a previously existing or new User
    """

    slug = serializers.SlugField(required=False,
        help_text=_("Username"),
        validators=[validators.RegexValidator(settings.ACCT_REGEX,
            _("Enter a valid username."), 'invalid')])
    #pylint:disable=protected-access
    email = serializers.EmailField(
        max_length=get_user_model()._meta.get_field('email').max_length,
        required=False,
        help_text=_("E-mail of user to grant role onto profile"\
            " (potentially generating an invite to the site)"))
    full_name = serializers.CharField(required=False,
        help_text=_("Full name of user to grant role onto profile"\
            " (potentially generating an invite to the site)"))
    message = serializers.CharField(max_length=255, required=False,
        help_text=_("Message to send along the invitation"))

    @staticmethod
    def validate_slug(data):
        # The ``slug`` / ``username`` is implicit in the addition of a role
        # for a newly created user while adding a role. Hence we don't return
        # a validation error if the length is too long but arbitrarly shorten
        # the username.
        user_model = get_user_model()
        #pylint:disable=protected-access
        max_length = user_model._meta.get_field('username').max_length
        if len(data) > max_length:
            if '@' in data:
                data = data.split('@')[0]
            data = data[:max_length]
        return data


class UploadBlobSerializer(NoModelSerializer):
    """
    Upload a picture or other POD content
    """
    location = serializers.URLField(
        help_text=_("URL to uploaded content"))


class AgreementSignSerializer(NoModelSerializer):

    read_terms = serializers.BooleanField(required=True,
        help_text=_("I have read and understand these terms and conditions"))
    last_signed = serializers.DateTimeField(read_only=True,
        help_text=_("Date/time of signature (in ISO format)"))

    class Meta:
        fields = ('read_terms', 'last_signed',)
        read_only = ('last_signed',)


class LifetimeSerializer(OrganizationSerializer):
    """
    A customer lifetime value
    """
    created_at = serializers.CharField(
        help_text=_("Since when is the profile a subscriber"))
    ends_at = serializers.CharField(
        help_text=_("Current end date for the contract"))
    contract_value = serializers.IntegerField(
        help_text=_("Total value to be collected from the profile"))
    cash_payments = serializers.IntegerField(
        help_text=_("Cash payments collected from the profile"))
    deferred_revenue = serializers.IntegerField(
        help_text=_("The deferred revenue for the profile"))
    unit = serializers.CharField(
        help_text=_("Three-letter ISO 4217 code for currency unit (ex: usd)"))

    class Meta(OrganizationSerializer.Meta):
        fields = OrganizationSerializer.Meta.fields + (
            'created_at', 'ends_at', 'contract_value',
            'cash_payments', 'deferred_revenue', 'unit')
        read_only_fields = ('created_at', 'ends_at', 'contract_value',
            'cash_payments', 'deferred_revenue', 'unit')


class ValidationErrorSerializer(NoModelSerializer):
    """
    Details on why token is invalid.
    """
    detail = serializers.CharField(help_text=_("Describes the reason for"\
        " the error in plain text"))


class OrganizationCartSerializer(NoModelSerializer):
    """
    Items which will be charged on an order checkout action.
    """
    processor = ProcessorAuthSerializer(required=False,
      help_text=_("Keys to authenticate the client with the payment processor"))
    results = InvoicableSerializer(many=True,
      help_text=_("Items that will be charged"))


class CheckoutItemSerializer(NoModelSerializer):
    option = serializers.IntegerField(
        help_text=_("selected plan option during checkout"))


class CheckoutSerializer(NoModelSerializer):
    """
    Processor token to charge the cart items.
    """
    items = CheckoutItemSerializer(required=False, many=True,
        help_text=_("List of indices, one per subscription that has multiple"\
        " advance discount options"))
    remember_card = serializers.BooleanField(required=False,
        help_text=_("attaches the payment method to the profile when true"))
    processor_token = serializers.CharField(required=False, max_length=255,
        help_text=_("one-time token generated by the processor"\
            "from the payment card."))
    street_address = serializers.CharField(required=False, allow_blank=True,
        help_text=_("Street address"))
    locality = serializers.CharField(required=False, allow_blank=True,
        help_text=_("City/Town"))
    region = serializers.CharField(required=False, allow_blank=True,
        help_text=_("State/Province/County"))
    postal_code = serializers.CharField(required=False, allow_blank=True,
        help_text=_("Zip/Postal code"))
    country = serializers.CharField(required=False, allow_blank=True,
        help_text=_("Country"))


class RedeemCouponSerializer(NoModelSerializer):
    """
    Serializer to redeem a ``Coupon``.
    """

    code = serializers.CharField(help_text=_("Coupon code to redeem"))

    def create(self, validated_data):
        return validated_data
