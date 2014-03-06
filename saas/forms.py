# Copyright (c) 2013, The DjaoDjin Team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
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

from saas.models import Plan
from saas.compat import User

class CreditCardForm(forms.Form):
    '''Update Card Information.'''
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
        self.fields['card_address_zip'] = forms.CharField(
            label='Zip', required=False)
        self.fields['card_address_country'] = forms.CharField(
            label='Country', required=False)
        self.fields['card_address_state'] = forms.CharField(
            label='State', required=False)


class PayNowForm(forms.Form):
    '''Pay amount on card'''
    amount = forms.FloatField(required=False)
    full_amount = forms.BooleanField(required=False)


class PlanForm(forms.ModelForm):
    """
    Form to create or update a ``Plan``.
    """
    class Meta:
        model = Plan
        exclude = [ 'discontinued_at', 'is_active', 'length', 'next_plan',
                    'organization', 'slug' ]

    def save(self, commit=True):
        if self.initial.has_key('organization'):
            self.instance.organization = self.initial['organization']
        self.instance.slug = slugify(self.cleaned_data['title'])
        return super(PlanForm, self).save(commit)


class UserForm(forms.ModelForm):
    """
    Form to update a ``User`` profile.
    """

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']


class UserRelationForm(forms.Form):
    '''Form to add/remove contributors and managers.'''
    username = forms.CharField()

