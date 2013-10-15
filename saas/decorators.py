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

"""Description of decorators that check a User a accepted specific
agreements."""

import logging, urlparse

from functools import wraps
from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib.auth import REDIRECT_FIELD_NAME, logout as auth_logout
from django.utils.decorators import available_attrs
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from django.contrib.sites.models import RequestSite, Site
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.template.loader import render_to_string
from registration.models import RegistrationProfile

from saas.models import Signature

LOGGER = logging.getLogger(__name__)

def _insert_url(request, redirect_field_name=REDIRECT_FIELD_NAME,
                inserted_url=None):
    '''Redirects to the *inserted_url* before going to the orginal
    request path.'''
    # This code is pretty much straightforward
    # from contrib.auth.user_passes_test
    path = request.build_absolute_uri()
    # If the login url is the same scheme and net location then just
    # use the path as the "next" url.
    login_scheme, login_netloc = urlparse.urlparse(inserted_url)[:2]
    current_scheme, current_netloc = urlparse.urlparse(path)[:2]
    if ((not login_scheme or login_scheme == current_scheme) and
        (not login_netloc or login_netloc == current_netloc)):
        path = request.get_full_path()
    from django.contrib.auth.views import redirect_to_login
    return redirect_to_login(path, inserted_url, redirect_field_name)


def _send_activation_email(registration_profile, site,
                           next_url=None,
                           redirect_field_name=REDIRECT_FIELD_NAME):
    """
    Send an activation email to the user associated
    with a ``RegistrationProfile``.

    The activation email embed a link to the activation url
    and a redirect to the page the activation email was sent
    from so that the user stays on her workflow once activation
    is completed.
    """
    context = {'activation_key': registration_profile.activation_key,
               'expiration_days': settings.ACCOUNT_ACTIVATION_DAYS,
               'site': site,
               REDIRECT_FIELD_NAME: next_url }
    subject = render_to_string(
        'registration/activation_email_subject.txt', context)
    # Email subject *must not* contain newlines
    subject = ''.join(subject.splitlines())
    message = render_to_string('registration/activation_email.txt', context)
    registration_profile.user.email_user(
        subject, message, settings.DEFAULT_FROM_EMAIL)


# The user we are looking to activate might be different from
# the request.user (which can be Anonymous)
def check_user_active(request, user,
                      redirect_field_name=REDIRECT_FIELD_NAME,
                      login_url=None):
    """
    Checks that the user is active. We won't activate the account of
    a user until we checked the email address is valid.
    """
    if not user.is_active:
        # Let's send e-mail again.
        try:
            registration_profile = RegistrationProfile.objects.get(
                user=user)
        except RegistrationProfile.DoesNotExist:
            # We might have corrupted the db by removing profiles
            # for inactive users. Let's just fix that here.
            registration_profile = \
                RegistrationProfile.objects.create_profile(user)
        if (registration_profile.activation_key
            != RegistrationProfile.ACTIVATED):
            if Site._meta.installed:
                site = Site.objects.get_current()
            else:
                site = RequestSite(request)
            _send_activation_email(
                registration_profile, site,
                next_url=request.META['PATH_INFO'],
                redirect_field_name=REDIRECT_FIELD_NAME)
            messages.info(
                request, _("A email has been sent to you with the "\
                           "steps to secure and activate your account."))
            return False
    return True


def active_required(redirect_field_name=REDIRECT_FIELD_NAME, login_url=None):
    """
    Decorator for views that checks that the user is active. We won't
    activate the account of a user until we checked the email address
    is valid.
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            if request.is_authenticated():
                if check_user_active(request, request.user):
                    return view_func(request, *args, **kwargs)
            return _insert_url(request, redirect_field_name,
                               login_url or settings.LOGIN_URL)
        return _wrapped_view
    return decorator


def requires_agreement(agreement, redirect_field_name=REDIRECT_FIELD_NAME,
                       login_url=None):
    """
    Decorator for views that checks that the user has signed a particular
    legal agreement, redirecting to the agreement signature or log-in page
    if necessary.
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated():
                if check_user_active(request, request.user):
                    # Check signature of the legal agreement
                    if Signature.objects.has_been_accepted(
                        agreement=agreement, user=request.user):
                        return view_func(request, *args, **kwargs)
                    return _insert_url(request, redirect_field_name,
                        reverse('legal_sign_agreement',
                                kwargs={'slug': agreement}))
                else:
                    # User is logged in but her email has not been verified yet.
                    auth_logout(request)
            return _insert_url(request, redirect_field_name,
                login_url or settings.LOGIN_URL)
        return _wrapped_view
    return decorator
