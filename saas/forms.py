# Copyright (c) 2013, Fortylines LLC
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

class CreditCardForm(forms.Form):
    '''Update Card Information.'''
    stripeToken = forms.CharField()

    def __init__(self, *args, **kwargs):
        #call our superclasse's initializer
        super(forms.Form, self).__init__(*args, **kwargs)
        #define other fields dinamically:
        self.fields['card-name'] = forms.CharField()
        self.fields['card-city'] = forms.CharField()
        self.fields['card-address-line1'] = forms.CharField()
        self.fields['card-address-country'] = forms.CharField()
        self.fields['card-address-state'] = forms.CharField()


class PayNowForm(forms.Form):
    '''Pay amount on card'''
    amount = forms.FloatField(required=False)
    full_amount = forms.BooleanField(required=False)


class UserRelationForm(forms.Form):
    '''Form to add/remove contributors and managers.'''
    username = forms.CharField()

