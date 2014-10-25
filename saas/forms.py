# Copyright (c) 2014, DjaoDjin inc.
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

from django import forms
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext_lazy as _
from django_countries import countries
from django_countries.fields import Country
import localflavor.us.forms as us_forms

from saas.models import Organization, Plan

#pylint: disable=super-on-old-class,no-member
#pylint: disable=old-style-class,no-init

class BankForm(forms.Form):
    """
    Update Bank Information
    """
    stripeToken = forms.CharField(required=False)


class PostalFormMixin(object):

    def add_postal_country(self, field_name='country', required=True):
        self.fields[field_name] = forms.CharField(
            widget=forms.widgets.Select(choices=countries),
            label='Country', required=required)

    def add_postal_region(self, field_name='region',
                          country=None, required=True):
        if country and country.code == "US":
            widget = us_forms.USPSSelect
        else:
            widget = forms.widgets.TextInput
        self.fields[field_name] = forms.CharField(
                widget=widget, label='State/Province', required=required)


class CreditCardForm(PostalFormMixin, forms.Form):
    """
    Update Card Information.
    """
    stripeToken = forms.CharField(required=False)
    remember_card = forms.BooleanField(
        label=_("Remember this card"), required=False, initial=True)

    def __init__(self, *args, **kwargs):
        #call our superclasse's initializer
        super(CreditCardForm, self).__init__(*args, **kwargs)
        #define other fields dynamically:
        self.fields['card_name'] = forms.CharField(
            label='Card Holder', required=False)
        self.fields['card_city'] = forms.CharField(
            label='City', required=False)
        self.fields['card_address_line1'] = forms.CharField(
            label='Street', required=False)
        self.add_postal_region(country=self.initial['country'], required=False)
        self.fields['card_address_zip'] = forms.CharField(
            label='Zip', required=False)
        self.add_postal_country(required=False)
        for item in self.initial:
            if item.startswith('cart-'):
                self.fields[item] = forms.CharField(required=True)


class CartPeriodsForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(CartPeriodsForm, self).__init__(*args, **kwargs)
        for item in self.initial:
            if item.startswith('cart-'):
                self.fields[item] = forms.CharField(required=True)


class OrganizationForm(PostalFormMixin, forms.ModelForm):

    class Meta:
        model = Organization
        fields = ('full_name', 'email', 'phone', 'street_address',
                  'locality', 'region', 'postal_code', 'country')
        widgets = {'country': forms.widgets.Select(choices=countries)}

    def __init__(self, *args, **kwargs):
        super(OrganizationForm, self).__init__(*args, **kwargs)
        if not (self.initial.has_key('country') and self.initial['country']):
            self.initial['country'] = Country("US", None)
        country = self.initial['country']
        if self.instance and self.instance.country:
            country = self.instance.country
        if not self.fields['country'].initial:
            self.fields['country'].initial = country.code
        self.add_postal_region(country=country)
        if self.initial.has_key('is_bulk_buyer'):
            initial = self.initial['is_bulk_buyer']
            if self.instance:
                initial = self.instance.is_bulk_buyer
            self.fields['is_bulk_buyer'] = forms.BooleanField(required=False,
                initial=initial,
                label="Enable this organization to pay subscriptions on behalf"\
" of others.")


class ManagerAndOrganizationForm(OrganizationForm):

    def __init__(self, *args, **kwargs):
        #call our superclasse's initializer
        super(ManagerAndOrganizationForm, self).__init__(*args, **kwargs)
        # XXX define other fields dynamically (username, etc.):
        # Unless it is not necessary?


class PlanForm(forms.ModelForm):
    """
    Form to create or update a ``Plan``.
    """
    class Meta:
        model = Plan
        exclude = ['discontinued_at', 'is_active', 'length', 'next_plan',
                   'organization', 'setup_amount', 'slug', 'transaction_fee']

    def save(self, commit=True):
        if self.initial.has_key('organization'):
            self.instance.organization = self.initial['organization']
        self.instance.slug = slugify(self.cleaned_data['title'])
        return super(PlanForm, self).save(commit)


class RedeemCouponForm(forms.Form):
    """
    Form used to redeem a coupon.
    """

    code = forms.CharField()


class UnsubscribeForm(forms.Form):
    """
    Form used to unsubscribe a customer from a plan.
    """

    plan = forms.SlugField()
    subscriber = forms.SlugField()


class UserRelationForm(forms.Form):
    '''Form to add/remove contributors and managers.'''
    username = forms.CharField()


class WithdrawForm(BankForm):
    """
    Withdraw amount from ``Funds`` to a bank account
    """
    amount = forms.FloatField(label="Amount (in $)", required=False)
