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

"""Extra Forms and Views that might prove useful to register users."""

from django import forms
from django.utils.translation import ugettext_lazy as _
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.context_processors import csrf
from django.utils.safestring import mark_safe
from django.template import RequestContext
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib import messages
import django.contrib.auth.forms
from registration import signals
from registration.backends.simple.views import RegistrationView \
    as BaseRegistrationView


class RegistrationForm(forms.Form):
    """
    Form for warming up registration of a new account. Just supply
    a full name and an email and you are in. We will ask for username
    and password later.
    """
    full_name = forms.RegexField(
        regex=r'^[\w\s]+$', max_length=60,
        widget=forms.TextInput(attrs={'placeholder':'Full Name'}),
        label=_("Full Name"),
        error_messages={ 'invalid':
            _("Sorry we do not recognize some characters in your full name.")})
    email = forms.EmailField(
        widget=forms.TextInput(attrs={'placeholder':'Email',
                                      'maxlength': 75}),
        label=_("E-mail"))

    def clean_email(self):
        """
        Check the supplied email address is unique.
        """
        user = User.objects.filter(email=self.cleaned_data['email'])
        if user.exists():
            raise forms.ValidationError(_("Account already registered!"))
        return self.cleaned_data['email']


class RegistrationView(BaseRegistrationView):
    """
    A registration backend which implements the simplest possible
    workflow: a user supplies a full name (first name and last name)
    and email address. The user is then immediately signed up and logged in).
    """
    def get(self, request, *args, **kwargs):
        return redirect(reverse('registration_register'))

    def form_invalid(self, form):
        messages.info(self.request, mark_safe(_("Coming back?"
                ' Please concider to <a href="%s">Sign up</a> or <a href="%s">Sign in</a>.' % (reverse('registration_register'), reverse('auth_login')))))
        #return redirect(reverse('registration_register'))
        return render(self.request, "registration/registration_form.html")

    def get_form_class(self, request):
        """
        Returns our custom registration form.
        """
        return RegistrationForm

    def register(self, request, **cleaned_data):
        full_name, email = cleaned_data['full_name'], cleaned_data['email']
        name_parts = full_name.split(' ')
        if len(name_parts) > 0:
            first_name = name_parts[0]
            last_name = ' '.join(name_parts[1:])
        else:
            first_name = full_name
            last_name = ''
        username = email
        try:
            new_user = User.objects.get(email=email)
        except User.DoesNotExists:
            new_user = User.objects.create_user(
                username, email, first_name=first_name, last_name=last_name)

        #new_user = authenticate(username=username, password=password)
        login(request, new_user)
        signals.user_registered.send(sender=self.__class__,
                                     user=new_user,
                                     request=request)
        return new_user
