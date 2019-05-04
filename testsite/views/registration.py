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

from django import forms
from django.conf import settings
from django.contrib.auth import (REDIRECT_FIELD_NAME, authenticate,
    get_user_model, login as auth_login)
from django.db import transaction
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.generic.edit import FormView
from django_countries import countries
from saas.models import Signature
from saas.utils import get_organization_model

#pylint:disable=no-name-in-module,import-error
from django.utils.six.moves.urllib.parse import urlparse


class PersonalRegistrationForm(forms.Form):
    """
    Form to register a user and organization (i.e. billing profile)
    at the same time.
    """

    username = forms.SlugField(max_length=30, label="Username",
        error_messages={'invalid': "username may only contain letters,"\
            " numbers and -/_ characters."})
    email = forms.EmailField(
        widget=forms.TextInput(attrs={'maxlength': 75}), label="E-mail")
    email2 = forms.EmailField(
        widget=forms.TextInput(attrs={'maxlength': 75}),
        label="E-mail confirmation")
    password = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(
        widget=forms.PasswordInput, label="Password confirmation")
    first_name = forms.CharField(label='First name', max_length=30)
    last_name = forms.CharField(label='Last name', max_length=30)
    street_address = forms.CharField(label='Street Addess')
    city = forms.CharField(label='City')
    region = forms.CharField(label='State/province')
    zip_code = forms.RegexField(label='Postal code', max_length=30,
        regex=r'^[\w-]+$',
        error_messages={
            'invalid': "The postal code may contain only letters, numbers "\
                         "and '-' characters."})
    country = forms.RegexField(regex=r'^[a-zA-Z ]+$',
        widget=forms.widgets.Select(choices=countries), label='Country')

    def clean(self):
        """
        Validates that both emails as well as both passwords respectively match.
        """
        if not ('email' in self._errors or 'email2' in self._errors):
            # If there are already errors reported for email or email2,
            # let's not override them with a confusing message here.
            email = self.cleaned_data.get('email', 'A')
            email2 = self.cleaned_data.get('email2', 'B')
            if email != email2:
                self._errors['email'] = self.error_class(["This field does"\
    " not match E-mail confirmation."])
                self._errors['email2'] = self.error_class(["This field does"\
    " not match E-mail."])
                if 'email' in self.cleaned_data:
                    del self.cleaned_data['email']
                if 'email2' in self.cleaned_data:
                    del self.cleaned_data['email2']
                raise forms.ValidationError(
                    "Email and E-mail confirmation do not match.")
        if not ('password' in self._errors or 'password2' in self._errors):
            password = self.cleaned_data.get('password', False)
            password2 = self.cleaned_data.get('password2', True)
            if password != password2:
                self._errors['password'] = self.error_class(["This field does"\
    " not match Password."])
                self._errors['password2'] = self.error_class(["This field does"\
    " not match Password confirmation."])
                if 'password' in self.cleaned_data:
                    del self.cleaned_data['password']
                if 'password2' in self.cleaned_data:
                    del self.cleaned_data['password2']
                raise forms.ValidationError(
                    "Password and Password confirmation do not match.")
        return self.cleaned_data

    def clean_email(self):
        """
        Normalizes emails in all lowercase.
        """
        if 'email' in self.cleaned_data:
            self.cleaned_data['email'] = self.cleaned_data['email'].lower()
        user = get_user_model().objects.filter(
            email__iexact=self.cleaned_data['email'])
        if user.exists():
            raise forms.ValidationError(
                "A user with that email already exists.")
        return self.cleaned_data['email']

    def clean_email2(self):
        """
        Normalizes emails in all lowercase.
        """
        if 'email2' in self.cleaned_data:
            self.cleaned_data['email2'] = self.cleaned_data['email2'].lower()
        return self.cleaned_data['email2']

    def clean_first_name(self):
        """
        Normalizes first names by capitalizing them.
        """
        if 'first_name' in self.cleaned_data:
            self.cleaned_data['first_name'] \
                = self.cleaned_data['first_name'].capitalize()
        return self.cleaned_data['first_name']

    def clean_last_name(self):
        """
        Normalizes first names by capitalizing them.
        """
        if 'last_name' in self.cleaned_data:
            self.cleaned_data['last_name'] \
                = self.cleaned_data['last_name'].capitalize()
        return self.cleaned_data['last_name']

    def clean_username(self):
        """
        Validate that the username is not already taken.
        """
        user = get_user_model().objects.filter(
            username=self.cleaned_data['username'])
        if user.exists():
            raise forms.ValidationError(
                "A user with that username already exists.")
        organization = get_organization_model().objects.filter(
            slug=self.cleaned_data['username'])
        if organization.exists():
            raise forms.ValidationError(
                "A profile with that username already exists.")

        return self.cleaned_data['username']


class PersonalRegistrationView(FormView):
    """
    Register a user, create an organization and associate the user as
    a manager for the organization.
    """

    form_class = PersonalRegistrationForm
    template_name = 'accounts/register.html'
    fail_url = ('registration_register', (), {})
    success_url = settings.LOGIN_REDIRECT_URL

    def get_context_data(self, **kwargs):
        context = super(PersonalRegistrationView, self).get_context_data(
            **kwargs)
        next_url = self.request.GET.get(REDIRECT_FIELD_NAME, None)
        if next_url:
            context.update({REDIRECT_FIELD_NAME: next_url})
        return context

    def form_valid(self, form):
        self.register(**form.cleaned_data)
        next_url = self.request.GET.get(REDIRECT_FIELD_NAME, None)
        if next_url:
            return HttpResponseRedirect(urlparse(next_url).path)
        return super(PersonalRegistrationView, self).form_valid(form)

    @method_decorator(transaction.atomic)
    def register(self, **cleaned_data):
        username = cleaned_data['username']
        password = cleaned_data['password']
        first_name = cleaned_data['first_name']
        last_name = cleaned_data['last_name']

        # Create a ``User``
        user = get_user_model().objects.create_user(
            username=username, password=password, email=cleaned_data['email'],
            first_name=first_name, last_name=last_name)

        terms_of_use = 'terms-of-use'
        Signature.objects.create_signature(terms_of_use, user)

        # Create a 'personal' ``Organization`` to associate the user
        # to a billing account.
        account = get_organization_model().objects.create(
            slug=username,
            full_name='%s %s' % (first_name, last_name),
            email=cleaned_data['email'],
            street_address=cleaned_data['street_address'],
            locality=cleaned_data['city'],
            region=cleaned_data['region'],
            postal_code=cleaned_data['zip_code'],
            country=cleaned_data['country'])
        account.add_manager(user)

        # Sign-in the newly registered user
        user = authenticate(username=username, password=password)
        auth_login(self.request, user)

        return user
