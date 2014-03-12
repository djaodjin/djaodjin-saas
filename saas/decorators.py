# Copyright (c) 2014, Fortylines LLC
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
We used to decorate the saas views with the "appropriate" decorators
except in many projects appropriate had a different meaning.

It turns out that the access control logic is better left to be configured
in the site URLConf through extensions like https://github.com/mila/django-urldecorators.
This is not only more flexible but also make security audits a lot easier.
"""

import logging, urlparse

from functools import wraps
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.contrib.sites.models import RequestSite, Site
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth import REDIRECT_FIELD_NAME, logout as auth_logout
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import available_attrs
from django.utils.translation import ugettext_lazy as _
from django.template.loader import render_to_string

from saas.models import Plan, Signature
from saas.views.auth import valid_manager_for_organization

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


def requires_agreement(function=None,
                       agreement='terms_of_use',
                       redirect_field_name=REDIRECT_FIELD_NAME,
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
                # Check signature of the legal agreement
                if Signature.objects.has_been_accepted(
                    agreement=agreement, user=request.user):
                    return view_func(request, *args, **kwargs)
                return _insert_url(request, redirect_field_name,
                                   reverse('legal_sign_agreement',
                                           kwargs={'slug': agreement}))
            return _insert_url(request, redirect_field_name,
                login_url or settings.LOGIN_URL)
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def requires_manager(function=None):
    """
    Decorator for views that checks that the user is a manager
    for the organization.
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            if kwargs.has_key('plan'):
                plan = get_object_or_404(Plan, slug=kwargs.get('plan'))
                organization = plan.organization
            elif kwargs.has_key('organization'):
                organization = kwargs.get('organization')
            organization = valid_manager_for_organization(
                request.user, organization)
            if organization:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def requires_paid_subscription(function=None,
                               redirect_field_name=REDIRECT_FIELD_NAME):
    """
    Decorator that checks a specificed subscription is paid.

    It redirects to an appropriate page when it is not. In case:
    - no charge is associated to the subscription => trigger payment
    - charge.status is failed                     => update card
    - charge.status is in-progress                => waiting
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            subscriber = None
            if kwargs.has_key('organization'):
                subscriber = valid_manager_for_organization(
                    request.user, kwargs.get('organization'))
            plan = None
            if kwargs.has_key('subscribed_plan'):
                plan = get_object_or_404(
                    Plan, slug=kwargs.get('subscribed_plan'))
            if subscriber and plan:
                subscription = get_object_or_404(Subscription,
                    organization=subscriber, plan=plan)
                if (not subscription.last_charge
                    or subscription.last_charge.state == Charge.FAILED
                    or subscription.last_charge.state == Charge.DISPUTED):
                    # No charge or a problem with the existing charge,
                    # we trigger a new charge.
                    return _insert_url(request, redirect_field_name,
                        reverse('saas_pay_subscription',
                            kwargs={'subscriber': subscriber, 'plan': plan}))
                elif subscription.last_charge.state == Charge.CREATED:
                    return _insert_url(request, redirect_field_name,
                        reverse('saas_wait_charge_state',
                            kwargs={'charge': subscription.last_charge}))

                return view_func(request, *args, **kwargs)
            raise Http404

        return _wrapped_view

    if function:
        return decorator(function)
    return decorator
