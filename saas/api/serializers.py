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
from __future__ import unicode_literals
from hashlib import sha256

from django.core import validators
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import is_password_usable
from django.template.defaultfilters import slugify
from django.utils import six
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from django_countries.serializer_fields import CountryField

from ..decorators import _valid_manager
from ..humanize import as_money
from ..mixins import as_html_description, product_url
from ..models import (BalanceLine, CartItem, Charge, Plan,
    RoleDescription, Subscription, Transaction)
from ..utils import (get_organization_model, get_role_model,
    get_picture_storage)

#pylint: disable=no-init,old-style-class

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

    def to_representation(self, obj):
        if isinstance(obj, list):
            result = [slugify(self.choices.get(item, None)) for item in obj]
        else:
            result = slugify(self.choices.get(obj, None))
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
                    'data': data, 'choices': [choice
                    for choice in six.iterkeys(self.inverted_choices)]})
        return result


class PlanRelatedField(serializers.RelatedField):

    def __init__(self, **kwargs):
        super(PlanRelatedField, self).__init__(
            queryset=Plan.objects.all(), **kwargs)

    # Django REST Framework 3.0
    def to_representation(self, obj):
        return obj.slug

    def to_internal_value(self, data):
        return get_object_or_404(Plan.objects.all(), slug=data)


class RoleDescriptionRelatedField(serializers.RelatedField):

    def __init__(self, **kwargs):
        super(RoleDescriptionRelatedField, self).__init__(**kwargs)

    # Django REST Framework 3.0
    def to_representation(self, obj):
        return obj.slug

    def to_internal_value(self, data):
        return get_object_or_404(RoleDescription.objects.all(), slug=data)


class NoModelSerializer(serializers.Serializer):

    def create(self, validated_data):
        raise RuntimeError('`create()` should not be called.')

    def update(self, instance, validated_data):
        raise RuntimeError('`update()` should not be called.')


class BalanceLineSerializer(serializers.ModelSerializer):

    class Meta:
        model = BalanceLine
        fields = ('title', 'selector', 'rank')
        extra_kwargs = {'selector': {'required': False}}


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


class CardSerializer(NoModelSerializer):
    """
    Information to verify a credit card
    """
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

    @staticmethod
    def get_readable_amount(charge):
        return as_money(charge.amount, charge.unit)

    class Meta:
        model = Charge
        fields = ('created_at', 'amount', 'unit', 'readable_amount',
                  'description', 'last4', 'exp_date', 'processor_key', 'state')


class EmailChargeReceiptSerializer(NoModelSerializer):
    """
    Response for the API call to send an e-mail duplicate to the customer.
    """
    charge_id = serializers.CharField(read_only=True,
        help_text=_("Charge identifier (i.e. matches the URL {charge}"\
            " parameter)"))
    email = serializers.EmailField(read_only=True,
        help_text=_("E-mail address to which the receipt was sent."))


class TableSerializer(NoModelSerializer):

    # XXX use `key` instead of `slug` here?
    key = serializers.CharField(
        help_text=_("Unique key in the table for the data series"))
    selector = serializers.CharField(
        help_text=_("Filter on the Transaction accounts"))
    values = serializers.CharField(
        help_text=_("Datapoints in the serie"))


class MetricsSerializer(NoModelSerializer):

    scale = serializers.FloatField(
        help_text=_("The scale of the number reported in the tables (ex: 1000"\
        " when numbers are reported in thousands of dollars)"))
    unit = serializers.CharField(
        help_text=_("Three-letter ISO 4217 code for currency unit (ex: usd)"))
    title = serializers.CharField(
        help_text=_("Title for the table"))
    table = TableSerializer(many=True)


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
    lines = RefundChargeItemSerializer(many=True)


class OrganizationSerializer(serializers.ModelSerializer):

    # If we put ``slug`` in the ``read_only_fields``, it will be set ``None``
    # when one creates an opt-in subscription.
    # If we don't define ``slug`` here, the serializer validators will raise
    # an exception "Organization already exists in database".
    slug = serializers.CharField(required=False, allow_blank=True,
        help_text=_("Unique identifier shown in the URL bar"))
    full_name = serializers.CharField(
        help_text=_("Full name"))
    default_timezone = serializers.CharField(required=False,
         help_text=_("Timezone to use when reporting metrics"))
    email = serializers.EmailField(
        help_text=_("E-mail address for the organization"))
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
    extra = serializers.CharField(required=False, allow_null=True,
        help_text=_("Extra meta data (can be stringify JSON)"))
    printable_name = serializers.CharField(read_only=True)
    credentials = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = get_organization_model()
        fields = ('slug', 'created_at', 'full_name',
            'email', 'phone', 'street_address', 'locality',
            'region', 'postal_code', 'country',
            'default_timezone', 'printable_name',
            'is_provider', 'is_bulk_buyer', 'type', 'credentials',
            'extra')
        read_only_fields = ('created_at',)

    @staticmethod
    def get_credentials(obj):
        if hasattr(obj, 'credentials'):
            return bool(obj.credentials)
        if hasattr(obj, 'user'):
            return is_password_usable(obj.user.password)
        return False

    def get_type(self, obj):
        if not obj.pk:
            return 'user'
        if hasattr(obj, 'is_personal') and obj.is_personal:
            return 'personal'
        return 'organization'

OrganizationSerializer._declared_fields["type"] = \
    serializers.SerializerMethodField(
        help_text=_("One of 'organization', 'personal' or 'user'"))


class CreateOrganizationSerializer(NoModelSerializer):
    # We have a special serializer for Create (i.e. POST request)
    # because we want to include the `type` field.

    slug = serializers.CharField(required=False, allow_blank=True,
        help_text=_("Unique identifier shown in the URL bar"))
    full_name = serializers.CharField(
        help_text=_("Full name"))
    default_timezone = serializers.CharField(required=False,
         help_text=_("Timezone to use when reporting metrics"))
    email = serializers.EmailField(
        help_text=_("E-mail address for the organization"))
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
    extra = serializers.CharField(required=False, allow_null=True,
        help_text=_("Extra meta data (can be stringify JSON)"))

    def validate_type(self, value):
        if value not in ('personal', 'organization'):
            raise ValidationError(
                _("type must be one of 'personal' or 'organization'."))
        return value

CreateOrganizationSerializer._declared_fields["type"] = \
    serializers.CharField(
        help_text=_("One of 'organization', 'personal' or 'user'"))


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


class OrganizationWithSubscriptionsSerializer(OrganizationSerializer):

    subscriptions = WithSubscriptionSerializer(
        source='subscription_set', many=True, read_only=True)

    def __init__(self, *args, **kwargs):
        super(OrganizationWithSubscriptionsSerializer, self).__init__(
            *args, **kwargs)
        obj = kwargs.get('data')
        if obj:
            # means serializer was populated with data
            storage = get_picture_storage()
            picture = obj.get('picture')
            if picture:
                name = '%s.%s' % (sha256(picture.read()).hexdigest(), 'jpg')
                storage.save(name, picture)
                kwargs['data']['picture'] = storage.url(name)

    class Meta:
        model = get_organization_model()
        fields = ('slug', 'created_at', 'full_name',
            'email', 'phone', 'street_address', 'locality',
            'region', 'postal_code', 'country', 'default_timezone',
            'printable_name', 'is_provider', 'is_bulk_buyer', 'type',
            'picture', 'extra', 'subscriptions')
        read_only_fields = ('slug', 'created_at',)


class OrganizationWithEndsAtByPlanSerializer(serializers.ModelSerializer):
    """
    Operational information on an Organization,
    bundled with its active subscriptions.
    """

    subscriptions = WithEndsAtByPlanSerializer(
        source='get_ends_at_by_plan', many=True, read_only=True)

    class Meta:
        model = get_organization_model()
        fields = ('slug', 'printable_name', 'created_at',
            'email', 'subscriptions', )
        read_only_fields = ('slug', 'created_at')


class PlanSerializer(serializers.ModelSerializer):

    title = serializers.CharField(required=False,
        help_text=_("Title for the plan"))
    description = serializers.CharField(required=False,
        help_text=_("Free-form text description for the plan"))
    is_active = serializers.BooleanField(required=False,
        help_text=_("True when customers can subscribe to the plan"))
    setup_amount = serializers.IntegerField(required=False,
        help_text=_("One-time amount to pay when the subscription starts"))
    period_amount = serializers.IntegerField(required=False,
        help_text=_("Amount billed every period"))
    # XXX rename `interval` to `period`
    interval = EnumField(choices=Plan.INTERVAL_CHOICES, required=False,
        help_text=_("Natural period for the subscription"))
    renewal_type = EnumField(choices=Plan.RENEWAL_CHOICES, required=False,
        help_text=_("Natural period for the subscription"))
    app_url = serializers.SerializerMethodField()
    organization = serializers.SlugRelatedField(
        read_only=True, slug_field='slug',
        help_text=_("Provider of the plan"))

    class Meta:
        model = Plan
        fields = ('slug', 'title', 'description', 'is_active',
                  'setup_amount', 'period_amount', 'interval', 'app_url',
                  'advance_discount', 'unit', 'organization', 'extra',
                  'period_length', 'renewal_type', 'is_not_priced',
                  'created_at')
        read_only_fields = ('slug', 'app_url')

    @staticmethod
    def get_app_url(obj):
        return product_url(obj.organization)

    def validate_title(self, title):
        kwargs = {}
        if 'provider' in self.context:
            kwargs.update({'organization': self.context['provider']})
        try:
            exists = Plan.objects.get(title=title, **kwargs)
            if self.instance is None or exists.pk != self.instance.pk:
                # Rename is ok.
                raise ValidationError(
                    _("A plan with this title already exists."))
        except Plan.DoesNotExist:
            pass
        return title



class SubscriptionSerializer(serializers.ModelSerializer):

    organization = OrganizationSerializer(read_only=True)
    plan = PlanSerializer(read_only=True)
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


class TransactionSerializer(serializers.ModelSerializer):
    """
    A `Transaction` in the double-entry bookkeeping ledger.
    """

    orig_organization = serializers.SlugRelatedField(
        read_only=True, slug_field='slug', help_text=_("Source organization"\
        " from which funds are withdrawn"))
    dest_organization = serializers.SlugRelatedField(
        read_only=True, slug_field='slug', help_text=_("Target organization"\
        " to which funds are deposited"))
    description = serializers.CharField(source='descr', read_only=True,
        help_text=_("Free-form text description for the transaction"))
    amount = serializers.CharField(source='dest_amount', read_only=True,
        help_text=_("Amount being transfered"))
    is_debit = serializers.CharField(source='dest_amount', read_only=True,
        help_text=_("True if the transaction is indentified as a debit in"\
        " the API context"))

    def _is_debit(self, transaction):
        """
        True if the transaction can be tagged as a debit. That is
        it is either payable by the organization or the transaction
        moves from a Funds account to the organization's Expenses account.
        """
        #pylint: disable=no-member
        if ('view' in self.context
            and hasattr(self.context['view'], 'organization')):
            return transaction.is_debit(self.context['view'].organization)
        return False

    def to_representation(self, obj):
        ret = super(TransactionSerializer, self).to_representation(obj)
        is_debit = self._is_debit(obj)
        if is_debit:
            amount = as_money(obj.orig_amount, '-%s' % obj.orig_unit)
        else:
            amount = as_money(obj.dest_amount, obj.dest_unit)
        ret.update({
            'description': as_html_description(obj),
            'is_debit': is_debit,
            'amount': amount})
        return ret

    class Meta:
        model = Transaction
        fields = ('created_at', 'description', 'amount', 'is_debit',
            'orig_account', 'orig_organization', 'orig_amount', 'orig_unit',
            'dest_account', 'dest_organization', 'dest_amount', 'dest_unit')


class UserSerializer(serializers.ModelSerializer):

    # Only way I found out to remove the ``UniqueValidator``. We are not
    # interested to create new instances here.
    slug = serializers.CharField(source='username', validators=[
        validators.RegexValidator(r'^[\w.@+-]+$', _('Enter a valid username.'),
            'invalid')],
        help_text=_("Effectively the username. The variable is named `slug`"\
            " such that front-end code can be re-used between Organization"\
            " and User records."))
    email = serializers.EmailField(read_only=True,
        help_text=_("E-mail address for the user"))
    created_at = serializers.DateTimeField(source='date_joined', required=False,
        help_text=_("Date/time of creation (in ISO format)"))
    full_name = serializers.SerializerMethodField(
        help_text=_("Full name for the contact (effectively first name"\
        " followed by last name)"))

    class Meta:
        model = get_user_model()
        fields = ('slug', 'email', 'full_name', 'created_at')
        read_only = ('full_name', 'created_at',)

    @staticmethod
    def get_full_name(obj):
        return obj.get_full_name()


class CartItemSerializer(serializers.ModelSerializer):
    """
    serializer for ``Coupon`` use metrics.
    """
    user = UserSerializer(required=False)
    plan = PlanRelatedField(read_only=False, required=True)

    class Meta:
        model = CartItem
        fields = ('created_at', 'user', 'plan',
            'option', 'full_name', 'sync_on')


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

    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = RoleDescription
        fields = ('created_at', 'title', 'slug', 'is_global', 'organization')


class AccessibleSerializer(serializers.ModelSerializer):
    """
    Formats an entry in a list of ``Organization`` accessible by a ``User``.
    """
    slug = serializers.SlugField(source='organization.slug')
    printable_name = serializers.CharField(source='organization.printable_name')
    email = serializers.CharField(source='organization.email')
    role_description = RoleDescriptionSerializer(read_only=True)

    class Meta:
        model = get_role_model()
        fields = ('created_at', 'request_key', 'grant_key',
            'slug', 'printable_name', 'email', # Organization
            'role_description')                # RoleDescription
        read_only_fields = ('created_at', 'request_key', 'grant_key',
            'printable_name')


class BaseRoleSerializer(serializers.ModelSerializer):

    user = UserSerializer(read_only=True)

    class Meta:
        model = get_role_model()
        fields = ('created_at', 'user', 'request_key', 'grant_key')
        read_only_fields = ('created_at', 'request_key', 'grant_key')


class RoleSerializer(BaseRoleSerializer):

    organization = OrganizationSerializer(read_only=True)
    role_description = RoleDescriptionRelatedField(read_only=True)

    class Meta(BaseRoleSerializer.Meta):
        fields = BaseRoleSerializer.Meta.fields + (
            'organization', 'role_description')
        read_only_fields = BaseRoleSerializer.Meta.read_only_fields + (
            'role_description',)


class RoleAccessibleSerializer(BaseRoleSerializer):
    role_description = RoleDescriptionSerializer(read_only=True)

    class Meta:
        model = get_role_model()
        fields = ('created_at', 'request_key', 'grant_key',
            'role_description', 'user')


class ValidationErrorSerializer(NoModelSerializer):
    """
    Details on why token is invalid.
    """
    detail = serializers.CharField(help_text=_("Describes the reason for"\
        " the error in plain text"))
