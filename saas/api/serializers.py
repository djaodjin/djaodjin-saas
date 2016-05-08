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

from django.core import validators
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from ..compat import User
from ..mixins import product_url
from ..models import BalanceLine, CartItem, Organization, Plan, Subscription
from ..utils import get_role_model

#pylint: disable=no-init,old-style-class

class PlanRelatedField(serializers.RelatedField):

    def __init__(self, **kwargs):
        super(PlanRelatedField, self).__init__(
            queryset=Plan.objects.all(), **kwargs)

    # Django REST Framework 3.0
    def to_representation(self, obj):
        return obj.slug

    def to_internal_value(self, data):
        return get_object_or_404(Plan, slug=data)


class BalanceLineSerializer(serializers.ModelSerializer):

    class Meta:
        model = BalanceLine
        fields = ('title', 'selector', 'rank')


class OrganizationSerializer(serializers.ModelSerializer):

    printable_name = serializers.CharField(read_only=True)

    class Meta:
        model = Organization
        fields = ('slug', 'full_name', 'printable_name', 'created_at', 'email')
        read_only_fields = ('slug',)


class WithSubscriptionSerializer(serializers.ModelSerializer):

    plan = serializers.SlugRelatedField(read_only=True, slug_field='slug')

    class Meta:
        model = Subscription
        fields = ('created_at', 'ends_at', 'plan', 'auto_renew')


class OrganizationWithSubscriptionsSerializer(serializers.ModelSerializer):

    subscriptions = WithSubscriptionSerializer(
        source='subscription_set', many=True, read_only=True)

    class Meta:
        model = Organization
        fields = ('slug', 'full_name', 'printable_name', 'created_at',
            'email', 'subscriptions', )
        read_only_fields = ('slug', )


class PlanSerializer(serializers.ModelSerializer):

    app_url = serializers.SerializerMethodField()
    description = serializers.CharField(required=False)
    is_active = serializers.BooleanField(required=False)

    class Meta:
        model = Plan
        fields = ('slug', 'title', 'description', 'is_active',
                  'setup_amount', 'period_amount', 'interval', 'app_url')
        read_only_fields = ('slug', 'app_url')

    @staticmethod
    def get_app_url(obj):
        return product_url(obj.organization)


class SubscriptionSerializer(serializers.ModelSerializer):

    organization = OrganizationSerializer(read_only=True)
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = ('created_at', 'ends_at', 'description',
                  'organization', 'plan', 'auto_renew')


class UserSerializer(serializers.ModelSerializer):

    # Only way I found out to remove the ``UniqueValidator``. We are not
    # interested to create new instances here.
    slug = serializers.CharField(source='username', validators=[
        validators.RegexValidator(r'^[\w.@+-]+$', _('Enter a valid username.'),
            'invalid')])
    created_at = serializers.DateTimeField(source='date_joined', required=False)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('slug', 'email', 'full_name', 'created_at')
        read_only = ('full_name', 'created_at',)

    @staticmethod
    def get_full_name(obj):
        return obj.get_full_name()


class CartItemSerializer(serializers.ModelSerializer):
    """
    serializer for ``Coupon`` use metrics.
    """
    user = UserSerializer()
    plan = PlanRelatedField(read_only=False, required=True)

    class Meta:
        model = CartItem
        fields = ('user', 'plan', 'created_at')


class RoleSerializer(serializers.ModelSerializer):

    organization = OrganizationSerializer(read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = get_role_model()
        fields = ('created_at', 'organization', 'user', 'name',
            'request_key', 'grant_key')
        read_only_fields = ('created_at', 'name', 'request_key', 'grant_key')
