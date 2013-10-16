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

"""Extra Forms and Views that might prove useful to register users."""

from django import forms
from django.utils.translation import ugettext_lazy as _
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.context_processors import csrf
from django.utils.safestring import mark_safe
from django.template import RequestContext
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login
from django.contrib import messages
from django.contrib.sites.models import RequestSite, Site
import django.contrib.auth.forms
from django.contrib.auth.tokens import default_token_generator
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.cache import never_cache
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth import authenticate
from registration import signals
from registration.models import RegistrationProfile, SHA1_RE
from registration.views import ActivationView as BaseActivationView
from registration.backends.simple.views import RegistrationView \
    as BaseRegistrationView

from saas.decorators import check_user_active

class RegistrationForm(forms.Form):
    """
    Form for frictionless registration of a new account. Just supply
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


class RegistrationView(BaseRegistrationView):
    """
    A frictionless registration backend With a full name and email
    address, the user is immediately signed up and logged in.
    """
    def get(self, request, *args, **kwargs):
        return redirect(reverse('registration_register'))

    def form_invalid(self, form):
        messages.error(
            self.request, _("Please enter a valid name and email address."))
        return redirect(reverse('registration_register'))

    def get_form_class(self, request):
        """
        Returns our custom registration form.
        """
        return RegistrationForm

    def get_success_url(self, request, user):
        # Because the user returned by register() might be None
        return ('accounts_profile', (), {})

    def register(self, request, **cleaned_data):
        full_name, email = cleaned_data['full_name'], cleaned_data['email']
        name_parts = full_name.split(' ')
        if len(name_parts) > 0:
            first_name = name_parts[0]
            last_name = ' '.join(name_parts[1:])
        else:
            first_name = full_name
            last_name = ''
        # XXX create a random username
        username = email

        users = User.objects.filter(email=email)
        if users.exists():
            user = users[0]
            if check_user_active(request, user):
                messages.info(request, mark_safe(_(
                    'An account with this email has already been registered! '\
                    'Please <a href="%s">login</a>' % reverse('auth_login'))))
            return None

        if Site._meta.installed:
            site = Site.objects.get_current()
        else:
            site = RequestSite(request)
        new_user = RegistrationProfile.objects.create_inactive_user(
            username, email, password=None, site=site)
        new_user.first_name = first_name
        new_user.last_name = last_name
        new_user.save()
        signals.user_registered.send(
            sender=self.__class__, user=new_user, request=request)

        # Bypassing authentication here, we are doing frictionless registration
        # the first time around.
        new_user.backend = 'django.contrib.auth.backends.ModelBackend'
        auth_login(request, new_user)
        return new_user


class ActivationView(BaseActivationView):
    """
    The user is now on the activation url that was sent in an email.
    It is time to activate the account.
    """

    token_generator = default_token_generator

    def activate(self, request, activation_key):
        self.activation_key = activation_key
        if SHA1_RE.search(activation_key):
            try:
                profile = RegistrationProfile.objects.get(
                    activation_key=activation_key)
                if not profile.activation_key_expired():
                    user = profile.user
                    if user.password == '!':
                        messages.info(self.request,
                            _("Please set a password to protect your account."))
                    else:
                        activated = RegistrationProfile.objects.activate_user(
                            activation_key)
                        if activated:
                            signals.user_activated.send(
                                sender=profile, user=activated, request=request)
                        messages.info(self.request,
                            _("Thank you. Your account is now activate." \
                                  " You can sign in at your convienience."))
                    return user
            except RegistrationProfile.DoesNotExist:
                return False
        return False

    def get_success_url(self, request, user):
        if user.password == '!':
            url = reverse('registration_password_confirm',
                          args=(self.activation_key,
                                self.token_generator.make_token(user)))
        else:
            url = reverse('auth_login')
        next_url = request.GET.get(REDIRECT_FIELD_NAME, None)
        if next_url:
            return "%s?%s=%s" % (url, REDIRECT_FIELD_NAME, next_url)
        return url


@sensitive_post_parameters()
@never_cache
def registration_password_confirm(request, activation_key, token=None,
        template_name='registration/password_reset_confirm.html',
        token_generator=default_token_generator,
        set_password_form=SetPasswordForm,
        post_reset_redirect=None,
        extra_context=None,
        redirect_field_name=REDIRECT_FIELD_NAME):
    """
    View that checks the hash in a password activation link and presents a
    form for entering a new password. We can activate the account for real
    once we know the email is valid and a password has been set.
    """
    user = None
    profile = None
    redirect_to = request.REQUEST.get(redirect_field_name, None)
    if SHA1_RE.search(activation_key):
        profile = RegistrationProfile.objects.get(activation_key=activation_key)
        if not profile.activation_key_expired():
            user = profile.user

    if user is not None and token_generator.check_token(user, token):
        validlink = True
        if request.method == 'POST':
            form = set_password_form(user, request.POST)
            if form.is_valid():
                form.save()
                activated = RegistrationProfile.objects.activate_user(activation_key)
                if activated:
                    signals.user_activated.send(
                        sender=profile, user=activated, request=request)

                # Okay, security check complete. Log the user in.
                user_with_backend = authenticate(
                    username=user.username,
                    password=form.cleaned_data.get('new_password1'))
                auth_login(request, user_with_backend)
                if request.session.test_cookie_worked():
                    request.session.delete_test_cookie()

                if redirect_to is None:
                    redirect_to = reverse('accounts_profile')
                return redirect(redirect_to)
        else:
            form = set_password_form(None)
    else:
        validlink = False
        form = None
    context = {
        'form': form,
        'validlink': validlink,
    }
    if redirect_to:
        context.update({redirect_field_name: redirect_to})
    if extra_context is not None:
        context.update(extra_context)
    return render(request, template_name, context)

