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

"""
Forms shown by the saas application
"""
from __future__ import unicode_literals

from decimal import Decimal

from django import forms
from django.template.defaultfilters import slugify
from django.utils.safestring import mark_safe
from django_countries import countries
from django_countries.fields import Country
import localflavor.us.forms as us_forms
from phonenumber_field.formfields import PhoneNumberField

from . import settings
from .compat import gettext_lazy as _
from .models import AdvanceDiscount, Plan, Subscription
from .utils import get_organization_model

#pylint: disable=no-member,no-init

class PhoneField(PhoneNumberField):

    def __init__(self, *args, **kwargs):
        region = kwargs.get('region')
        if not region:
            params = {'region': 'US'}
            params.update(kwargs)
        else:
            params = kwargs
        super(PhoneField, self).__init__(*args, **params)


class BankForm(forms.ModelForm):
    """
    Update Bank Information
    """
    form_id = 'bank-form'
    stripeToken = forms.CharField(
        required=False, widget=forms.widgets.HiddenInput())

    class Meta:
        model = get_organization_model()
        fields = tuple([])


class PostalFormMixin(object):

    def add_postal_country(self, field_name='country', required=True):
        self.fields[field_name] = forms.CharField(
            widget=forms.widgets.Select(choices=countries),
            label=_("Country"), required=required)

    def add_postal_region(self, field_name='region',
                          country=None, required=True):
        if country and country.code == "US":
            widget = us_forms.USPSSelect
        else:
            widget = forms.widgets.TextInput
        if field_name in self.fields:
            self.fields[field_name].widget = widget()
        else:
            self.fields[field_name] = forms.CharField(widget=widget,
                label=_("State/Province/County"), required=required)



class CreditCardForm(PostalFormMixin, forms.Form):
    """
    Update Card Information.
    """
    stripeToken = forms.CharField(required=False)
    razorpay_payment_id = forms.CharField(required=False)
    remember_card = forms.BooleanField(
        label=_("Remember this card"), required=False, initial=True)

    def __init__(self, *args, **kwargs):
        #call our superclasse's initializer
        super(CreditCardForm, self).__init__(*args, **kwargs)
        #define other fields dynamically:
        self.fields['card_name'] = forms.CharField(
            label=_("Card Holder"), required=False)
        self.fields['card_city'] = forms.CharField(
            label=_("City/Town"), required=False)
        self.fields['card_address_line1'] = forms.CharField(
            label=_("Street address"), required=False)
        self.add_postal_region(country=self.initial['country'], required=False)
        self.fields['card_address_zip'] = forms.CharField(
            label=_("Zip/Postal code"), required=False)
        self.add_postal_country(required=False)
        for item in self.initial:
            if item.startswith('cart-'):
                self.fields[item] = forms.CharField(required=True)

    def clean_remember_card(self):
        remember_card = self.data.get('remember_card', None)
        if remember_card is not None:
            self.cleaned_data['remember_card'] = (
                remember_card not in ("0", "off"))
        return self.cleaned_data['remember_card']


class VTChargeForm(CreditCardForm):

    amount = forms.CharField()
    descr = forms.CharField()

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        try:
            self.cleaned_data['amount'] = int(Decimal(amount) * 100)
        except (TypeError, ValueError) as err:
            raise forms.ValidationError(
                _("'%(amount)s' is an invalid amount (%(err)s)") % {
                    'amount': amount, 'err': err})
        return self.cleaned_data['amount']


class CartPeriodsForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(CartPeriodsForm, self).__init__(*args, **kwargs)
        for item in self.initial:
            if item.startswith('cart-'):
                self.fields[item] = forms.CharField(required=True)


class ImportTransactionForm(forms.Form):

    subscription = forms.CharField()
    created_at = forms.DateTimeField()
    amount = forms.DecimalField()
    descr = forms.CharField(required=False)

    def clean_subscription(self):
        parts = self.cleaned_data['subscription'].split(Subscription.SEP)
        if len(parts) != 2:
            raise forms.ValidationError(
                _("Subscription should be of the form subscriber:plan."))
        return self.cleaned_data['subscription']

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        try:
            self.cleaned_data['amount'] = int(Decimal(amount) * 100)
        except (TypeError, ValueError):
            raise forms.ValidationError(_("Invalid amount"))
        return self.cleaned_data['amount']



class OrganizationForm(PostalFormMixin, forms.ModelForm):

    submit_title = _('Update')
    slug = forms.SlugField(max_length=254, label=_("Display name"),
        disabled=True,
        error_messages={'invalid': _("Display name may only contain letters,"\
            " digits and -/_ characters. Spaces are not allowed.")})
    street_address = forms.CharField(label=_("Street address"), required=False)
    phone = PhoneField(label=_("Phone number"), required=False)

    class Meta:
        model = get_organization_model()
        fields = ('slug', 'full_name', 'email', 'phone', 'country',
                  'region', 'locality', 'street_address', 'postal_code')
        widgets = {'country': forms.widgets.Select(choices=countries)}

    def __init__(self, *args, **kwargs):
        super(OrganizationForm, self).__init__(*args, **kwargs)
        if kwargs.get('instance', None) is None:
            self.submit_title = _('Create')
        if 'country' in self.fields:
            # Country field is optional. We won't add a State/Province
            # in case it is omitted.
            if not ('country' in self.initial
                and self.initial['country']):
                self.initial['country'] = Country("US", None)
            country = self.initial.get('country', None)
            if self.instance and self.instance.country:
                country = self.instance.country
            if not self.fields['country'].initial:
                self.fields['country'].initial = country.code
            self.add_postal_region(country=country)
        if 'is_bulk_buyer' in self.initial:
            initial = self.initial['is_bulk_buyer']
            if self.instance:
                initial = self.instance.is_bulk_buyer
            self.fields['is_bulk_buyer'] = forms.BooleanField(required=False,
                initial=initial,
                label=mark_safe(_("Enable GroupBuy (<a href=\""\
"https://djaodjin.com/docs/#group-billing\" target=\"_blank\">what is it?</a>)"
                )))
        if 'is_provider' in self.initial:
            initial = self.initial['is_provider']
            if self.instance:
                initial = self.instance.is_provider
            self.fields['is_provider'] = forms.BooleanField(required=False,
                label=_("Enable creation of subscription plans"),
                initial=initial)
        if 'extra' in self.initial:
            initial = self.initial['extra']
            if self.instance:
                initial = self.instance.extra
            self.fields['extra'] = forms.CharField(required=False,
                widget=forms.Textarea, label=mark_safe('Notes'),
                initial=initial)


class OrganizationCreateForm(OrganizationForm):

    slug = forms.SlugField(label=_("Display name"),
        help_text=_("Unique identifier shown in the URL bar"))

    class Meta:
        model = get_organization_model()
        fields = ('slug', 'full_name', 'email')


class ManagerAndOrganizationForm(OrganizationForm):

    def __init__(self, *args, **kwargs):
        super(ManagerAndOrganizationForm, self).__init__(*args, **kwargs)
        self.fields['full_name'].label = 'Full name'
        # XXX define other fields dynamically (username, etc.):
        # Unless it is not necessary?


class PlanForm(forms.ModelForm):
    """
    Form to create or update a ``Plan``.
    """
    submit_title = _("Update")

    period_type = forms.ChoiceField(choices=[
        (slugify(choice[1]), choice[1]) for choice in Plan.INTERVAL_CHOICES])
    renewal_type = forms.ChoiceField(choices=[
        (slugify(choice[1]), choice[1]) for choice in Plan.RENEWAL_CHOICES])
    unit = forms.ChoiceField(choices=(
        ('usd', 'usd'), ('cad', 'cad'), ('eur', 'eur')))
    period_amount = forms.DecimalField(max_digits=7, decimal_places=2)
    advance_discount_type = forms.ChoiceField(choices=[
        (slugify(choice[1]), choice[1])
        for choice in AdvanceDiscount.DISCOUNT_CHOICES])
    advance_discount_value = forms.DecimalField(max_digits=5, decimal_places=2)
    advance_discount_length = forms.IntegerField()

    class Meta:
        model = Plan
        fields = ('title', 'description', 'period_amount', 'unit',
                  'period_type', 'period_length', 'renewal_type',
                  'advance_discount_type', 'advance_discount_value',
                  'advance_discount_length')

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial', None)
        if initial:
            period_amount = initial.get('period_amount', 0)
            period_type = initial.get('period_type', Plan.MONTHLY)
            renewal_type = initial.get('renewal_type', Plan.AUTO_RENEW)
            advance_discount_type = initial.get(
                'advance_discount_type', AdvanceDiscount.PERCENTAGE)
            advance_discount_value = initial.get(
                'advance_discount_value', 0)
            advance_discount_length = initial.get(
                'advance_discount_value', 0)
        instance = kwargs.get('instance', None)
        if instance:
            period_amount = instance.period_amount
            period_type = instance.period_type
            renewal_type = instance.renewal_type
            advance_discount = instance.advance_discounts.first()
            if advance_discount:
                advance_discount_type = advance_discount.discount_type
                advance_discount_value = advance_discount.discount_value
                advance_discount_length = advance_discount.length
        else:
            self.submit_title = _("Create")
        period_amount = Decimal(period_amount).scaleb(-2)
        period_type = slugify(Plan.INTERVAL_CHOICES[period_type - 1][1])
        renewal_type = slugify(Plan.RENEWAL_CHOICES[renewal_type][1])
        advance_discount_type = slugify(
            AdvanceDiscount.DISCOUNT_CHOICES[advance_discount_type - 1][1])
        if advance_discount_type in (AdvanceDiscount.PERCENTAGE,
                                     AdvanceDiscount.CURRENCY):
            advance_discount_value = Decimal(advance_discount_value).scaleb(-2)
        initial.update({
            'period_amount':period_amount,
            'period_type': period_type,
            'renewal_type': renewal_type,
            'advance_discount_type': advance_discount_type,
            'advance_discount_value': advance_discount_value,
            'advance_discount_length': advance_discount_length
        })
        super(PlanForm, self).__init__(*args, **kwargs)

    def clean_advance_discount_value(self):
        try:
            if self.cleaned_data['advance_discount_type'] in (
                    AdvanceDiscount.PERCENTAGE, AdvanceDiscount.CURRENCY):
                self.cleaned_data['advance_discount_value'] = \
                    int(self.cleaned_data['advance_discount_value'].scaleb(2))
            else:
                self.cleaned_data['advance_discount_value'] = \
                    int(self.cleaned_data['advance_discount_value'])
        except (TypeError, ValueError):
            self.cleaned_data['advance_discount_value'] = 0
        return self.cleaned_data['advance_discount_value']

    def clean_period_type(self):
        period_type = self.cleaned_data['period_type']
        for period_choice in Plan.INTERVAL_CHOICES:
            if period_type == slugify(period_choice[1]):
                self.cleaned_data['period_type'] = period_choice[0]
                return self.cleaned_data['period_type']
        raise forms.ValidationError(
            _("period must be one of %(period)s") % {[
                period_choice[1] for period_choice in Plan.INTERVAL_CHOICES]})

    def clean_period_amount(self):
        try:
            self.cleaned_data['period_amount'] = \
              int(self.cleaned_data['period_amount'].scaleb(2))
        except (TypeError, ValueError):
            self.cleaned_data['period_amount'] = 0
        return self.cleaned_data['period_amount']

    def clean_renewal_type(self):
        renewal_type = self.cleaned_data['renewal_type']
        for renewal_type_choice in Plan.RENEWAL_CHOICES:
            if renewal_type == slugify(renewal_type_choice[1]):
                self.cleaned_data['renewal_type'] = renewal_type_choice[0]
                return self.cleaned_data['renewal_type']
        raise forms.ValidationError(
            _("renewal must be one of %(type)s") % {
                'type': [renewal_type_choice[1]
            for renewal_type_choice in Plan.RENEWAL_CHOICES]})

    def clean_title(self):
        kwargs = {}
        if 'organization' in self.initial:
            kwargs.update({'organization': self.initial['organization']})
        try:
            exists = Plan.objects.get(
                title=self.cleaned_data['title'], **kwargs)
            if self.instance is None or exists.pk != self.instance.pk:
                # Rename is ok.
                raise forms.ValidationError(
                    _("A plan with this title already exists."))
        except Plan.DoesNotExist:
            pass
        return self.cleaned_data['title']

    def save(self, commit=True):
        if 'organization' in self.initial:
            self.instance.organization = self.initial['organization']
        return super(PlanForm, self).save(commit)


class RedeemCouponForm(forms.Form):
    """
    Form used to redeem a coupon.
    """
    submit_title = _("Redeem")

    code = forms.CharField(label=_("Registration code"))


class UserRelationForm(forms.Form):
    """
    Form to add/remove managers and other custom roles.
    """
    username = forms.CharField()


class WithdrawForm(BankForm):
    """
    Withdraw amount from ``Funds`` to a bank account
    """
    submit_title = _("Withdraw")
    amount = forms.DecimalField(required=False)

    def __init__(self, *args, **kwargs):
        #call our superclasse's initializer
        super(WithdrawForm, self).__init__(*args, **kwargs)
        self.fields['amount'].label = _("Amount (in %(unit)s)") % {
            'unit': kwargs.get('initial', {}.get(
                'unit', settings.DEFAULT_UNIT))}
