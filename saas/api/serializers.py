# Copyright (c) 2025, DjaoDjin inc.
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

import json, logging

from django.core import validators
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import is_password_usable
from django.db import transaction, IntegrityError
from django.template.defaultfilters import slugify
from django_countries.serializer_fields import CountryField
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
import phonenumbers

from .. import settings
from ..compat import gettext_lazy as _, is_authenticated, reverse, six
from ..decorators import _valid_manager
from ..humanize import MONTHLY, as_money
from ..mixins import as_html_description, product_url, read_agreement_file
from ..models import (get_broker, AdvanceDiscount, Agreement, BalanceLine,
    CartItem, Charge, Coupon, Plan, RoleDescription, Subscription, Transaction,
    UseCharge)
from ..utils import (build_absolute_uri, get_organization_model, get_role_model,
    get_user_serializer, get_user_detail_serializer, handle_uniq_error)


LOGGER = logging.getLogger(__name__)


class EnumField(serializers.ChoiceField):
    """
    Treat a ``PositiveSmallIntegerField`` as an enum.
    """
    translated_choices = {}

    def __init__(self, choices, *args, **kwargs):
        self.translated_choices = {key: slugify(val) for key, val in choices}
        super(EnumField, self).__init__([(slugify(val), key)
            for key, val in choices],
            *args, **kwargs)

    def to_representation(self, value):
        if isinstance(value, list):
            result = [slugify(self.translated_choices.get(item, None))
                for item in value]
        else:
            result = slugify(self.translated_choices.get(value, None))
        return result

    def to_internal_value(self, data):
        if isinstance(data, list):
            result = [self.choices.get(item, None) for item in data]
        else:
            result = self.choices.get(data, None)
        if result is None:
            if not data:
                raise ValidationError(_("This field cannot be blank."))
            raise ValidationError(_("'%(data)s' is not a valid choice."\
                " Expected one of %(choices)s.") % {
                    'data': data, 'choices': [str(choice)
                    for choice in six.iterkeys(self.choices)]})
        return result


class ExtraField(serializers.CharField):

    def to_internal_value(self, data):
        if isinstance(data, dict):
            try:
                return json.dumps(data)
            except (TypeError, ValueError):
                pass
        return super(ExtraField, self).to_internal_value(data)

    def to_representation(self, value):
        if isinstance(value, dict):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            pass
        return super(ExtraField, self).to_representation(value)


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

    default_error_messages = {
      'required': _('This field is required.'),
      'does_not_exist': _("Plan '{pk_value}' does not exist or is inactive."),
    }

    def __init__(self, **kwargs):
        is_active = kwargs.pop('is_active', None)
        super(PlanRelatedField, self).__init__(
            queryset=Plan.objects.filter(is_active=True) if is_active
            else Plan.objects.all(), **kwargs)

    def to_representation(self, value):
        return value.slug

    def to_internal_value(self, data):
        try:
            return self.queryset.get(slug=data)
        except Plan.DoesNotExist:
            self.fail('does_not_exist', pk_value=data)
        return None


class UseChargeRelatedField(serializers.RelatedField):

    default_error_messages = {
      'required': _('This field is required.'),
      'does_not_exist':
        _("UseCharge '{pk_value}' does not exist or is inactive."),
    }

    def __init__(self, **kwargs):
        super(UseChargeRelatedField, self).__init__(
            queryset=UseCharge.objects.all(), **kwargs)

    def to_representation(self, value):
        return value.slug

    def to_internal_value(self, data):
        try:
            return self.queryset.get(slug=data)
        except UseCharge.DoesNotExist:
            self.fail('does_not_exist', pk_value=data)
        return None


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


class AtTimeSerializer(NoModelSerializer):

    at_time = serializers.DateTimeField(required=False,
      help_text=_("Date/time at which action is recorded (in ISO 8601 format)"))


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
    processor_info = ProcessorAuthSerializer(required=False,
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
        help_text=_("Country as 2-letter code (ISO 3166-1)"))


class PlanSerializer(serializers.ModelSerializer):

    slug = serializers.SlugField(required=False,
        help_text=_("Unique identifier shown in the URL bar"))
    title = serializers.CharField(required=False,
        help_text=_("Title for the plan"))

    class Meta:
        model = Plan
        fields = ('slug', 'title',)


class CouponSerializer(serializers.ModelSerializer):
    """
    Serializer to retrieve or update a `Coupon`.
    """
    code = serializers.CharField(required=False,
        help_text=_("Unique identifier per provider, typically used in URLs"))
    discount_type = EnumField(choices=Coupon.DISCOUNT_CHOICES,
        help_text=_("Type of discount ('percentage', 'currency', or 'period')"))
    plan = PlanSerializer(required=False, allow_null=True,
        help_text=_("Coupon will only apply to this plan"))

    class Meta:
        model = Coupon
        fields = ('code', 'discount_type', 'discount_value',
            'created_at', 'ends_at', 'description',
            'nb_attempts', 'plan')


class CouponUpdateSerializer(CouponSerializer):
    """
    Serializer to update a coupon
    """
    plan = PlanRelatedField(required=False, allow_null=True,
        help_text=_("Coupon will only apply to this plan"))

    @staticmethod
    def validate_plan(plan):
        if plan and not plan.is_active:
            raise ValidationError(_("The plan is inactive. "\
                "As a result the coupon will have no effect."))
        return plan

    class Meta(CouponSerializer.Meta):
        model = CouponSerializer.Meta.model
        fields = CouponSerializer.Meta.fields


class CouponCreateSerializer(CouponUpdateSerializer):
    """
    Serializer to create a coupon, including the `code`.
    """
    code = serializers.CharField(required=True,
        help_text=_("Unique identifier per provider, typically used in URLs"))
    discount_type = EnumField(required=True, choices=Coupon.DISCOUNT_CHOICES,
        help_text=_("Type of discount ('percentage', 'currency', or 'period')"))
    discount_value = serializers.IntegerField(required=True,
        help_text=_("Amount of the discount"))

    class Meta(CouponUpdateSerializer.Meta):
        model = CouponUpdateSerializer.Meta.model
        fields = CouponUpdateSerializer.Meta.fields


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


class KeyValueTuple(serializers.ListField):
    # `KeyValueTuple` is typed as a (String, Integer) tuple.
    # by not specifying a child field, the serialized data
    # is generated as expected. Otherwise we would end up
    # with a (String, String).

    min_length = 2
    max_length = 3


class TableSerializer(NoModelSerializer):

    slug = serializers.SlugField(
        help_text=_("Unique key in the table for the data series"))
    title = serializers.CharField(required=False, read_only=True,
        help_text=_("Title of data serie that can be safely used for display"\
        " in HTML pages"))
    extra = ExtraField(required=False, read_only=True,
        help_text=_("Extra meta data (can be stringify JSON)"))
    values = serializers.ListField(
        child=KeyValueTuple(),
        help_text=_("List of (datetime, integer) couples that represents"\
        " the data serie"))
    # XXX only in balances.py
    selector = serializers.CharField(
        required=False,
        help_text=_("Filter on transaction accounts"))


class MetricsSerializer(NoModelSerializer):

    scale = serializers.FloatField(required=False,
        help_text=_("The scale of the number reported in the tables (ex: 1000"\
        " when numbers are reported in thousands of dollars)"))
    unit = serializers.CharField(required=False,
        help_text=_("Three-letter ISO 4217 code for currency unit (ex: usd)"))
    title = serializers.CharField(
        help_text=_("Title for the table"))
    results = TableSerializer(many=True,
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


class WithEndsAtByPlanSerializer(NoModelSerializer):

    plan = serializers.SlugField(source='plan__slug', read_only=True)
    ends_at = serializers.DateTimeField(source='ends_at__max', read_only=True)

    class Meta:
        fields = ('plan', 'ends_at')


class WithSubscriptionSerializer(serializers.ModelSerializer):

    plan = PlanSerializer(read_only=True,
        help_text=_("Plan the profile is subscribed to"))

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
    printable_name = serializers.SerializerMethodField(
        help_text=_("Name that can be safely used for display in HTML pages"))
    credentials = serializers.SerializerMethodField(
        help_text=_("True if the account has valid login credentials"))

    class Meta:
        model = get_organization_model()
        fields = ('slug', 'printable_name', 'picture', 'type', 'credentials',
            'created_at')
        read_only_fields = ('printable_name', 'type', 'credentials',
            'created_at')

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
    serializers.SerializerMethodField(#pylint:disable=protected-access,no-member
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
        help_text=_("Country as 2-letter code (ISO 3166-1)"))
    is_bulk_buyer = serializers.BooleanField(required=False, default=False,
        help_text=_("Enable GroupBuy"))
    extra = ExtraField(required=False, allow_null=True,
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
    serializers.CharField(#pylint:disable=protected-access,no-member
        required=False,
        help_text=_("One of 'organization', 'personal' or 'user'"))


class OrganizationWithSubscriptionsSerializer(OrganizationDetailSerializer):
    """
    Operational information on an Organization,
    bundled with its subscriptions.
    """
    subscriptions = WithSubscriptionSerializer(many=True, read_only=True,
        help_text=_("Active subscriptions for the profile"))

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


class UseChargeSerializer(serializers.ModelSerializer):

    # If we don't override `validators` here, using PlanDetailSerializer
    # for updates will return a `ValidationError(code='unique')` when processing
    # `use_charges` in `serializer.is_valid(raise_exception=True)`.
    slug = serializers.SlugField(validators=[
        validators.RegexValidator(settings.ACCT_REGEX,
            _("Enter a valid slug."), 'invalid')],
        help_text=_("Unique identifier shown in the URL bar"))

    class Meta:
        model = UseCharge
        fields = ('slug', 'title', 'description', 'created_at',
            'use_amount', 'quota', 'maximum_limit', 'extra')


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
    profile = OrganizationSerializer(source='organization', read_only=True,
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
    use_charges = UseChargeSerializer(many=True, required=False,
        help_text=_("Variable pricing based on usage"))
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
            'setup_amount', 'period_amount', 'period_type',
            'advance_discounts', 'use_charges', 'unit', 'profile', 'extra',
            'period_length', 'renewal_type', 'is_not_priced', 'unlock_event',
            'created_at', 'skip_optin_on_grant', 'optin_on_request',
            'discounted_period_amount', 'is_cart_item', 'detail')
        read_only_fields = ('discounted_period_amount', 'is_cart_item',
            'detail')

    @staticmethod
    def get_discounted_period_amount(obj):
        return getattr(obj, 'discounted_period_amount', obj.period_amount)

    @staticmethod
    def get_is_cart_item(obj):
        return getattr(obj, 'is_cart_item', False)

    def create(self, validated_data):
        advance_discounts = validated_data.pop('advance_discounts', [])
        use_charges = validated_data.pop('use_charges', [])
        with transaction.atomic():
            instance = Plan.objects.create(**validated_data)
            for advance_discount in advance_discounts:
                AdvanceDiscount.objects.create(
                    plan=instance,
                    discount_type=advance_discount.get('discount_type'),
                    discount_value=advance_discount.get('discount_value'),
                    length=advance_discount.get('length'))
            for use_charge in use_charges:
                UseCharge.objects.create(
                    plan=instance,
                    slug=use_charge.get('slug'),
                    title=use_charge.get('title'),
                    description=use_charge.get('description', ""),
                    use_amount=use_charge.get('use_amount', 0),
                    quota=use_charge.get('quota', 0),
                    maximum_limit=use_charge.get('maximum_limit'),
                    extra=use_charge.get('extra'))

        return instance

    def update(self, instance, validated_data):
        advance_discounts = validated_data.pop('advance_discounts', [])
        use_charges = validated_data.pop('use_charges', [])
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

            instance.use_charges.exclude(slug__in=[
                use_charge.get('slug') for use_charge in use_charges]).delete()
            for use_charge in use_charges:
                use_charge_slug = use_charge.get('slug')
                try:
                    UseCharge.objects.update_or_create(
                        defaults={
                            'title': use_charge.get('title'),
                            'description': use_charge.get('description'),
                            'use_amount': use_charge.get('use_amount'),
                            'quota': use_charge.get('quota'),
                            'maximum_limit': use_charge.get('maximum_limit'),
                            'extra': use_charge.get('extra')
                        },
                        plan=instance, slug=use_charge_slug)
                except IntegrityError as err:
                    handle_uniq_error(err)
        return instance


class PlanCreateSerializer(PlanDetailSerializer):
    """
    Serializer to create plans in POST requests
    """
    title = serializers.CharField(required=True,
        help_text=_("Title for the plan"))

    class Meta(PlanDetailSerializer.Meta):
        fields = PlanDetailSerializer.Meta.fields

    def validate(self, attrs):
        period_type = attrs.get('period_type',
            Plan.INTERVAL_CHOICES[MONTHLY - 1][1])
        period_amount = attrs.get('period_amount', 0)

        min_amount = getattr(settings, 'BROKER_MINIMUM_PLAN_AMOUNT_%s' %
            period_type, 0)
        if min_amount and period_amount < min_amount:
            raise ValidationError(
                _('Period amount must be greater or equal to %(min_amount)s.')
                % {'min_amount': min_amount})

        return attrs


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
    # Implementation Note: As a comment to avoid API docgen
    # to pick it up as a replacement of the field description.
    #
    # Base class to serialize `Subscription` instances.
    #
    # The actual serializer used in API endpoints will either
    # be `SubscribedSubscriptionSerializer` for subscriber-side APIs
    # or `ProvidedSubscriptionSerializer` for provider-side APIs.

    # XXX used to be OrganizationDetailSerializer. because it is used
    # in checkout with group buy, do we need the e-mail?
    profile = OrganizationSerializer(source='organization',
        read_only=True,
        help_text=_("Profile subscribed to the plan"))
    plan = PlanSerializer(read_only=True,
        help_text=_("Plan the profile is subscribed to"))
    app_url = serializers.SerializerMethodField(
      help_text=_("URL to access the subscribed service"))

    class Meta:
        model = Subscription
        fields = ('created_at', 'ends_at', 'description',
                  'profile', 'plan', 'auto_renew',
                  'extra', 'grant_key', 'request_key',
                  'app_url')
        # XXX grant_key and request_key should probably be removed.
        read_only_fields = ('grant_key', 'request_key')

    def get_app_url(self, obj):
        return product_url(subscriber=obj.organization, plan=obj.plan,
            request=self.context['request'])


class SubscribedSubscriptionSerializer(SubscriptionSerializer):

    remove_api_url = serializers.SerializerMethodField(
        help_text=_("URL API endpoint to remove the subscription request"))

    # `editable` is only subscribed-side since all APIs provider-side
    # will by definition return subscribers / subscriptions a profile manager
    # for the plan provider has permission to.
    editable = serializers.SerializerMethodField(
        help_text=_("True if the request user is able to update the"\
        " subscription. Typically a profile manager for the plan provider."))

    class Meta(SubscriptionSerializer.Meta):
        fields = SubscriptionSerializer.Meta.fields + (
            'remove_api_url', 'editable')

    def get_editable(self, subscription):
        request = self.context['request']
        return bool(_valid_manager(
            request.user if is_authenticated(request) else None,
            [subscription.plan.organization]))

    def get_remove_api_url(self, obj):
        return build_absolute_uri(location=reverse(
            'saas_api_subscription_detail', args=(obj.organization, obj.plan,)),
            request=self.context['request'])


class ProvidedSubscriptionSerializer(SubscriptionSerializer):

    accept_request_api_url = serializers.SerializerMethodField(
        help_text=_("URL API endpoint to grant the subscription"))
    remove_api_url = serializers.SerializerMethodField(
        help_text=_("URL API endpoint to remove the subscription grant"))

    class Meta(SubscriptionSerializer.Meta):
        fields = SubscriptionSerializer.Meta.fields + (
            'accept_request_api_url', 'remove_api_url')

    def get_accept_request_api_url(self, obj):
        if obj.request_key:
            return build_absolute_uri(location=reverse(
                'saas_api_subscription_grant_accept', args=(
                obj.plan.organization, obj.request_key)),
                request=self.context['request'])
        return None

    def get_remove_api_url(self, obj):
        return build_absolute_uri(location=reverse(
            'saas_api_plan_subscription', args=(
                obj.plan.organization, obj.plan, obj.organization)),
                request=self.context['request'])


class ProvidedSubscriptionDetailSerializer(SubscriptionSerializer):
    """
    For active subscriptions we return the contact information for the profile.
    """
    profile = OrganizationDetailSerializer(source='organization',
        read_only=True,
        help_text=_("Profile subscribed to the plan"))

    class Meta(SubscriptionSerializer.Meta):
        pass


class ProvidedSubscriptionCreateSerializer(serializers.ModelSerializer):

    profile = OrganizationInviteSerializer(source='organization',
        help_text=_("Profile subscribed to the plan"))
    message = serializers.CharField(required=False, allow_null=True,
        help_text=_("Message to send along the invitation"))

    class Meta:
        model = Subscription
        fields = ('profile', 'message')


class TransactionSerializer(serializers.ModelSerializer):
    """
    A `Transaction` in the double-entry bookkeeping ledger.
    """

    orig_profile = OrganizationSerializer(source='orig_organization',
        read_only=True,
        help_text=_("Billing profile from which funds are withdrawn"))
    dest_profile = OrganizationSerializer(source='dest_organization',
        read_only=True,
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
            'description': as_html_description(instance,
                request=self.context.get('request')),
            'is_debit': is_debit,
            'amount': amount})
        return ret

    class Meta:
        model = Transaction
        fields = ('created_at', 'description', 'amount', 'is_debit',
            'orig_account', 'orig_profile', 'orig_amount', 'orig_unit',
            'dest_account', 'dest_profile', 'dest_amount', 'dest_unit')


class ChargeItemSerializer(NoModelSerializer):

    invoiced = TransactionSerializer(
        help_text=_("Transaction invoiced"))
    refunded = TransactionSerializer(many=True,
        help_text=_("Array of transactions with refunds"))


class InvoicableSubscriptionSerializer(SubscriptionSerializer):
    """
    Serializer for `Subscription` which are presented as part of an invoicable
    """
    plan = PlanDetailSerializer(read_only=True,
        help_text=_("Plan the profile is subscribed to"))


class InvoicableSerializer(NoModelSerializer):
    """
    serializer for an invoicable item with available options.
    """
    subscription = InvoicableSubscriptionSerializer(read_only=True, help_text=_(
        "Subscription lines and options refer to."))
    lines = TransactionSerializer(many=True, help_text=_(
        "Line items to charge on checkout."))
    options = TransactionSerializer(read_only=True, many=True, help_text=(
        "Options to replace line items."))


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
        fields = ('created_at', 'amount', 'unit', 'state', 'readable_amount',
            'description', 'claim_code', 'last4', 'exp_date', 'processor_key',
            'detail')
        read_only_fields = ('created_at', 'amount', 'unit', 'readable_amount',
            'description', 'claim_code', 'last4', 'exp_date', 'processor_key',
            'state', 'detail')


class CartItemSerializer(serializers.ModelSerializer):
    """
    serializer for a ``CartItem`` object.

    This serializer is typically used in coupon performance metrics.
    """
    user = get_user_serializer()(
        help_text=_("User the cart belongs to"))
    plan = PlanSerializer(help_text=_("Plan in the cart"))
    use = UseChargeSerializer(required=False, allow_null=True,
        help_text=_("Use charge in the cart"))

    detail = serializers.SerializerMethodField(read_only=True, required=False,
        help_text=_("Describes the result of the action"\
            " in human-readable form"))

    class Meta:
        model = CartItem
        fields = ('created_at', 'user', 'plan', 'use',
            'option', 'quantity', 'claim_code',
            'sync_on', 'full_name', 'email', 'detail')
        read_only_fields = ('created_at', 'user', 'claim_code', 'detail')

    @staticmethod
    def get_detail(obj):
        if hasattr(obj, 'detail'):
            return obj.detail
        if isinstance(obj, dict):
            return obj.get('detail')
        return None


class CartItemUpdateSerializer(CartItemSerializer):
    """
    Designed for handling update operations on cart items.
    Restricts user and plan fields to be read-only.
    """
    user = get_user_serializer()(
        help_text=_("User the cart belongs to"), read_only=True)
    plan = PlanSerializer(
        help_text=_("Plan in the cart (if any)"), read_only=True)

    class Meta(CartItemSerializer.Meta):
        read_only_fields = ('plan',) + CartItemSerializer.Meta.read_only_fields


class CartItemCreateSerializer(serializers.ModelSerializer):
    """
    Serializer to build a request.user set of plans to subscribe to (i.e. cart).
    """
    plan = PlanRelatedField(is_active=True, read_only=False, required=True,
        help_text=_("The plan to add into the request.user cart."))
    use = UseChargeRelatedField(required=False,
        help_text=_("The use charge to add into the request.user cart."))
    # Without declaring `created_at` we cannot override the creation date
    # even though the fields is not specified as read-only in the `Meta` class.
    created_at = serializers.DateTimeField(required=False,
      help_text=_("Date/time at which item is recorded (in ISO 8601 format)"))

    class Meta:
        model = CartItem
        fields = ('created_at', 'plan', 'option',
                  'use', 'quantity', 'sync_on', 'full_name', 'email')

    def validate(self, attrs):
        use = attrs.get('use')
        if use:
            plan = attrs.get('plan')
            if use.plan != plan:
                raise ValidationError(
                _("UseCharge %(use)s does not belong to plan %(plan)s")
                % {'use': use, 'plan': plan})
        return super(CartItemCreateSerializer, self).validate(attrs)


class UserCartItemCreateSerializer(CartItemCreateSerializer):
    """
    Extends `CartItemCreateSerializer` to include user.
    It's used during the creation of new cart items to
    ensure necessary data is captured.
    """
    user = serializers.SlugRelatedField(
        queryset=get_user_model().objects.all(),
        slug_field='username',
        required=True,
        help_text=_('The user for whom the cart item is being created')
    )

    class Meta(CartItemCreateSerializer.Meta):
        fields = ('user',) + CartItemCreateSerializer.Meta.fields

class CartItemUploadSerializer(NoModelSerializer):

    created = CartItemSerializer(many=True,
        help_text=_("Items that have been created in the cart"))
    updated = CartItemSerializer(many=True,
        help_text=_("Rows that have been uploaded"))
    failed = CartItemSerializer(many=True,
        help_text=_("Rows that have failed to be created in the cart"))


class RoleDescriptionSerializer(serializers.ModelSerializer):

    profile = OrganizationSerializer(source='organization', read_only=True,
        help_text=_("Profile the role type belongs to"))
    is_global = serializers.BooleanField(read_only=True,
        help_text=_("True when the role type is available for all profiles"))

    # `editable` means the request user can update / delete the role
    # description.
    editable = serializers.SerializerMethodField(
        help_text=_("True if the request user is able to update the"\
        " role description. Typically a profile manager"\
        " for the organization (local role description) or the broker"\
        " (global role descriptions)."))

    class Meta:
        model = RoleDescription
        fields = ('created_at', 'slug', 'title',
                  'skip_optin_on_grant', 'implicit_create_on_none',
                  'otp_required', 'is_global', 'profile', 'extra', 'editable')
        read_only_fields = ('created_at', 'slug', 'is_global', 'editable')

    def get_editable(self, obj):
        candidates = [get_broker()]
        try:
            if obj.organization:
                candidates += [obj.organization]
        except AttributeError:
            # serializers for notification will use this serializer,
            # though passing dictionnaries instead of an object.
            # the `editable` field was never intended for notifications
            # so it is ok to ignore here.
            pass
        # In notifications (triggered by signals), we will not have
        # `request` in the context either.
        if 'request' in self.context:
            request = self.context['request']
            return bool(_valid_manager(
                request.user if is_authenticated(request) else None,
                candidates))
        return False


class AccessibleSerializer(serializers.ModelSerializer):
    """
    Formats an entry in a list of ``Organization`` accessible by a ``User``.
    """
    profile = OrganizationSerializer(source='organization',# read_only=True,
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
            'profile', 'role_description',
            'home_url', 'settings_url',
            'accept_grant_api_url', 'remove_api_url')
        read_only_fields = ('created_at', 'request_key')

    def get_accept_grant_api_url(self, obj):
        if obj.grant_key:
            return build_absolute_uri(location=reverse(
                'saas_api_accessibles_accept', args=(obj.user, obj.grant_key)),
                request=self.context['request'])
        return None

    def get_remove_api_url(self, obj):
        role_description = (obj.role_description
            if obj.role_description else settings.MANAGER)
        return build_absolute_uri(location=reverse(
            'saas_api_accessible_detail', args=(
                obj.user, role_description, obj.organization)),
                request=self.context['request'])

    def get_settings_url(self, obj):
        req = self.context['request']
        org = obj.organization
        if org.is_provider:
            settings_location = build_absolute_uri(location=reverse(
                'saas_dashboard', args=(org.slug,)), request=req)
        else:
            settings_location = build_absolute_uri(location=reverse(
                'saas_organization_profile', args=(org.slug,)), request=req)
        return settings_location

    def get_home_url(self, obj):
        try:
            return obj.home_url
        except AttributeError:
            pass
        return product_url(subscriber=obj.organization,
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

    user = get_user_detail_serializer()(read_only=True,
        help_text=_("User with the role"))
    role_description = RoleDescriptionSerializer(read_only=True,
        help_text=_("Description of the role"))
    extra = ExtraField(required=False,
        help_text=_("Extra meta data (can be stringify JSON)"))
    accept_request_api_url = serializers.SerializerMethodField(
        help_text=_("URL API endpoint to grant the role"))
    remove_api_url = serializers.SerializerMethodField(
        help_text=_("URL API endpoint to remove the role grant or request"))
    detail = serializers.CharField(read_only=True, required=False,
        help_text=_("Describes the result of the action"\
            " in human-readable form"))

    class Meta:
        model = get_role_model()
        fields = ('created_at', 'user', 'extra', 'grant_key',
            'role_description', 'accept_request_api_url',
            'remove_api_url', 'detail')
        read_only_fields = ('created_at', 'grant_key', 'role_description',
            'detail')

    def get_accept_request_api_url(self, obj):
        if obj.request_key:
            return build_absolute_uri(location=reverse(
                'saas_api_roles_by_descr', args=(
                obj.organization, obj.role_description)),
                request=self.context['request'])
        return None

    def get_remove_api_url(self, obj):
        role_description = (obj.role_description
            if obj.role_description else settings.MANAGER)
        return build_absolute_uri(location=reverse('saas_api_role_detail',
            args=(obj.organization, role_description, obj.user)),
            request=self.context['request'])


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
    extra = ExtraField(required=False,
        help_text=_("Extra meta data (can be stringify JSON)"))
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


class EngagedSubscriberSerializer(RoleSerializer):
    """
    The engaged subscribers API gives users with a role to a subscriber
    that have logged in within a time period.
    """

    profile = OrganizationSerializer(source='organization',
        help_text=_("Profile the user has a role on"))

    class Meta(RoleSerializer.Meta):
        fields = RoleSerializer.Meta.fields + ('profile',)


class UploadBlobSerializer(NoModelSerializer):
    """
    Upload a picture or other POD content
    """
    location = serializers.URLField(
        help_text=_("URL to uploaded content"))


class AgreementSerializer(serializers.ModelSerializer):

    class Meta:
        model = Agreement
        fields = ('slug', 'title', 'updated_at')
        read_only_fields = ('slug', 'updated_at')


class AgreementDetailSerializer(AgreementSerializer):
    """
    Serializer to retrieve the text of an agreement
    """
    text = serializers.SerializerMethodField(
        help_text=_("Text of the agreement"))

    def get_text(self, obj):
        return read_agreement_file(obj.slug, request=self.context['request'])

    class Meta(AgreementSerializer.Meta):
        fields = AgreementSerializer.Meta.fields + ('text',)


class AgreementUpdateSerializer(AgreementSerializer):
    """
    Serializer to update an agreement
    """
    updated_at = serializers.DateTimeField(read_only=False,
        help_text=_("Date/time of update (in ISO 8601 format)"))

    class Meta(AgreementSerializer.Meta):
        model = AgreementSerializer.Meta.model
        fields = AgreementSerializer.Meta.fields


class AgreementCreateSerializer(AgreementUpdateSerializer):
    """
    Serializer to create an agreement
    """
    updated_at = serializers.DateTimeField(required=False,
        help_text=_("Date/time of update (in ISO 8601 format)"))

    class Meta(AgreementUpdateSerializer.Meta):
        model = AgreementUpdateSerializer.Meta.model
        fields = AgreementUpdateSerializer.Meta.fields


class AgreementSignSerializer(NoModelSerializer):

    read_terms = serializers.BooleanField(required=True,
        help_text=_("I have read and understand these terms and conditions"))
    last_signed = serializers.DateTimeField(read_only=True,
        help_text=_("Date/time of signature (in ISO 8601 format)"))

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


class ValidationDetailSerializer(NoModelSerializer):
    """
    Details on why token is invalid.
    """
    detail = serializers.CharField(help_text=_("Describes the reason for"\
        " the error in plain text"))


class OrganizationCartSerializer(NoModelSerializer):
    """
    Items which will be charged on an order checkout action.
    """
    processor_info = ProcessorAuthSerializer(required=False,
      help_text=_("Keys to authenticate the client with the payment processor"))
    results = InvoicableSerializer(many=True,
      help_text=_("Line items included in the invoice"))

    class Meta:
        fields = ('processor_info', 'results')
        read_only_fields = ('processor_info', 'results')


class PaymentSerializer(OrganizationCartSerializer):
    """
    Serializer for payment API
    """
    # All fields defined in `ChargeSerializer`
    claim_code = serializers.CharField(
        help_text=_("Unique identifier"))
    created_at = serializers.DateTimeField(
        help_text=_("Date/time of creation (in ISO 8601 format)"))
    amount = serializers.IntegerField(
        help_text=_("amount in unit"))
    unit = serializers.CharField(
        help_text=_("Three-letter ISO 4217 code for currency unit (ex: usd)"))
    state = serializers.CharField(source='get_state_display',
        help_text=_("Current state (i.e. created, done, failed, disputed)"))
    processor_key = serializers.CharField(allow_null=True,
        help_text=_("Unique identifier returned by the payment processor"))
    last4 = serializers.CharField(source='get_last4_display', read_only=True,
        help_text=_("Last 4 digits of the credit card used"))
    exp_date = serializers.CharField(
        help_text=_("Expiration date of the credit card on file"))
    readable_amount = serializers.SerializerMethodField(
        help_text=_("Amount and unit in a commonly accepted readable format"))

    class Meta(OrganizationCartSerializer.Meta):
        fields = OrganizationCartSerializer.Meta.fields + (
            'claim_code', 'created_at', 'amount', 'unit', 'state',
            'processor_key', 'last4', 'exp_date', 'readable_amount',
            'description')
        read_only_fields = OrganizationCartSerializer.Meta.fields + (
            'claim_code', 'created_at', 'amount', 'unit', 'state',
            'processor_key', 'last4', 'exp_date', 'readable_amount',
            'description')

    @staticmethod
    def get_readable_amount(charge):
        return as_money(charge.amount, charge.unit)


class CheckoutItemSerializer(NoModelSerializer):
    option = serializers.IntegerField(
        help_text=_("selected plan option during checkout"))


class PaylaterSerializer(NoModelSerializer):
    """
    Record an order of the cart items.
    """
    items = CheckoutItemSerializer(required=False, many=True,
        help_text=_("List of indices, one per subscription that has multiple"\
        " advance discount options"))
    street_address = serializers.CharField(required=False, allow_blank=True,
        help_text=_("Street address"))
    locality = serializers.CharField(required=False, allow_blank=True,
        help_text=_("City/Town"))
    region = serializers.CharField(required=False, allow_blank=True,
        help_text=_("State/Province/County"))
    postal_code = serializers.CharField(required=False, allow_blank=True,
        help_text=_("Zip/Postal code"))
    country = CountryField(required=False, allow_blank=True,
        help_text=_("Country as 2-letter code (ISO 3166-1)"))


class CheckoutSerializer(PaylaterSerializer):
    """
    Processor token to charge the cart items.
    """
    remember_card = serializers.BooleanField(required=False,
        help_text=_("attaches the payment method to the profile when true"))
    processor_token = serializers.CharField(required=False, max_length=255,
        help_text=_("one-time token generated by the processor"\
            "from the payment card."))



class RedeemCouponSerializer(NoModelSerializer):
    """
    Serializer to redeem a ``Coupon``.
    """

    code = serializers.CharField(help_text=_("Coupon code to redeem"))

    def create(self, validated_data):
        return validated_data


class BalancesDueSerializer(OrganizationSerializer):

    balances = serializers.DictField(
        help_text=_("Dictionary of balances due, keyed by unit"),
        read_only=True)

    class Meta(OrganizationSerializer.Meta):
        fields = OrganizationSerializer.Meta.fields + ('balances',)


# Serializers to document HTTP query parameters

class QueryParamActiveSerializer(NoModelSerializer):

    active = serializers.BooleanField(required=False,
        help_text=_("True when customers can subscribe to the plan"),
        default=None, allow_null=True)


class QueryParamCancelBalanceSerializer(NoModelSerializer):

    amount = serializers.IntegerField(required=False, min_value=1,
        help_text=_("Amount to mark as paid or write-off. Min value is 1."))
    paid = serializers.BooleanField(required=False,
        help_text=_("When true, the cancelation was recovered offline,"\
        " else it is a write-off"))


class QueryParamCartItemSerializer(NoModelSerializer):

    plan = PlanRelatedField(required=False, allow_null=True,
            help_text=_("Plan"))
    email = serializers.EmailField(required=False,
        help_text=_("E-mail address"), default=None, allow_null=True)


class QueryParamForceSerializer(NoModelSerializer):

    force = serializers.BooleanField(required=False,
        help_text=_("Forces invite of user/organization that could"\
        " not be found"))


class QueryParamPeriodSerializer(NoModelSerializer):

    ends_at = serializers.CharField(required=False,
        help_text=_("Data/time for the end of the period (in ISO format)"))

    period_type = EnumField(choices=Plan.INTERVAL_CHOICES, required=False,
        help_text=_("Natural period length"\
        " (hourly, daily, weekly, monthly, yearly). Defaults to monthly."))

    nb_periods = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        help_text=_("Specify the number of periods to include. "
        "Min value is 1."))


class QueryParamRoleStatusSerializer(NoModelSerializer):

    role_status = serializers.CharField(required=False, default='',
        allow_blank=True)


class QueryParamPersonalProfSerializer(NoModelSerializer):

    include_personal_profile = serializers.BooleanField(required=False,
            help_text=_("True when a personal profile should be shown"),
            default=None, allow_null=True)

    convert_from_personal = serializers.BooleanField(required=False,
            default=None, allow_null=True)


class QueryParamUpdateSerializer(NoModelSerializer):

    update = serializers.BooleanField(required=False,
        help_text=_("Adds context to update a payment method on file."))
