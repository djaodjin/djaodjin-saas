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

"""
The access control logic is best configured in the site URLConf through
extensions like `django-urldecorators`_. This is not only more flexible but
also make security audits a lot easier.

.. _django-urldecorators: https://github.com/mila/django-urldecorators
"""

import logging, urlparse

from functools import wraps
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.shortcuts import get_object_or_404
from django.utils.decorators import available_attrs

from . import settings
from .models import (Charge, Organization, Plan, Signature, Subscription,
    get_broker)
from .utils import datetime_or_now, get_roles


LOGGER = logging.getLogger(__name__)

# With ``WEAK`` authorization, contributors can issue POST, PUT, PATCH, DELETE
# requests. With ``NORMAL`` authorization, contributors can issue GET requests
# and nothing else. With ``STRONG`` authorization, contributors cannot issue
# any requests, only managers can.
WEAK = 0
NORMAL = 1
STRONG = 2

def _valid_role(user, candidates, role=settings.MANAGER):
    """
    Returns the subset of a set of ``Organization`` *candidates*
    which have *user* listed with a role.
    """
    results = []
    if settings.SKIP_PERMISSION_CHECK:
        if user:
            username = user.username
        else:
            username = '(none)'
        LOGGER.warning("Skip permission check for %s on organizations %s",
                       username, candidates)
        return candidates
    if user and user.is_authenticated():
        results = Organization.objects.filter(
            pk__in=get_roles(role).filter(
                user=user, organization__in=candidates).values(
                'organization')).values('slug')
    return results


def _valid_manager(user, candidates):
    """
    Returns the subset of a queryset of ``Organization``, *candidates*
    which have *user* as a manager.
    """
    return _valid_role(user, candidates, role=settings.MANAGER)


def _valid_contributor(user, candidates):
    """
    Returns a tuple made of two list of ``Organization`` from *candidates*.
    The first element contains organizations which have *user*
    as a manager. The second element contains organizations which have *user*
    as a contributor.
    """
    results = _valid_role(user, candidates, role=settings.CONTRIBUTOR)
    if settings.BYPASS_CONTRIBUTOR_CHECK:
        # So we can do live demos.
        for candidate in candidates:
            if str(candidate) in settings.BYPASS_CONTRIBUTOR_CHECK:
                if not isinstance(candidate, Organization):
                    candidate = get_object_or_404(Organization, slug=candidate)
                if not isinstance(results, list):
                    results = list(results)
                results += [candidate]
    return results


def _filter_valid_access(request, candidates, strength=NORMAL):
    """
    Returns a tuple made of two lists of ``Organization`` from *candidates*.

    The first item in the tuple are the organizations managed by *request.user*
    while the second item in the tuple are the organizations contributed to
    by *request.user*.

    The set of contributed organizations is further filtered by
    *request.method* and *strength*.
    """
    managed = []
    contributed = []
    managed = _valid_manager(request.user, candidates)
    if request.method == "GET":
        if strength != STRONG:
            contributed = _valid_contributor(request.user, candidates)
    else:
        if strength == WEAK:
            contributed = _valid_contributor(request.user, candidates)
    return managed, contributed


def _has_valid_access(request, candidates, strength=NORMAL):
    """
    Returns True if any candidate is accessible to the request user.
    """
    managed, contributed = _filter_valid_access(request, candidates, strength)
    return len(managed) + len(contributed) > 0


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
    # As long as *inserted_url* is not None, this call will redirect
    # anything (i.e. inserted_url), not just the login.
    from django.contrib.auth.views import redirect_to_login
    return redirect_to_login(path, inserted_url, redirect_field_name)


def fail_authenticated(request):
    if not request.user.is_authenticated():
        return reverse(settings.LOGIN_URL)
    return False


def fail_agreement(request, agreement=settings.TERMS_OF_USE):
    if not Signature.objects.has_been_accepted(
            agreement=agreement, user=request.user):
        return reverse('legal_sign_agreement', kwargs={'agreement': agreement})
    return False


def fail_paid_subscription(request, organization=None, plan=None):
    if _has_valid_access(request, [get_broker()]):
        # Bypass if a manager for the broker.
        return False
    if organization and not isinstance(organization, Organization):
        organization = get_object_or_404(Organization, slug=organization)
    if plan and not isinstance(plan, Plan):
        plan = get_object_or_404(Plan, slug=plan)
    subscribed_at = datetime_or_now()
    subscriptions = Subscription.objects.filter(
        organization=organization, plan=plan,
        ends_at__gt=subscribed_at)
    if not subscriptions.exists():
        return "%s?%s=%s" % (
            reverse('saas_cart_plan_list'), REDIRECT_FIELD_NAME,
            reverse('saas_organization_cart', args=(organization,)))
    if subscriptions.first().is_locked:
        return reverse(
            'saas_organization_balance', args=(organization, plan))
    return False


def fail_direct(request, charge=None, organization=None, strength=NORMAL):
    """
    Returns False if the request authenticated ``User`` is a direct contributor
    (or manager) for the ``Organization`` associated to the request.

    Managers can issue all types of requests (GET, POST, etc.) while
    contributors are restricted to GET requests.

    .. image:: perms-contrib.*
    """
    if charge:
        if not isinstance(charge, Charge):
            charge = get_object_or_404(Charge, processor_key=charge)
        organization = charge.customer
    elif organization:
        if not isinstance(organization, Organization):
            organization = get_object_or_404(Organization, slug=organization)
    else:
        organization = get_broker()
    result = not(organization and _has_valid_access(
        request, [organization], strength))
    return result


def fail_direct_weak(request, charge=None, organization=None):
    """
    Returns False if the request authenticated ``User``
    is a direct contributor (or manager) for the ``Organization`` associated
    to the request.

    Both managers and contributors can issue all types of requests
    (GET, POST, etc.).
    """
    return fail_direct(
        request, charge=charge, organization=organization, strength=WEAK)


def fail_direct_strong(request, charge=None, organization=None):
    """
    Returns True if the request authenticated ``User``
    is a direct manager for the ``Organization`` associated to the request.
    """
    return fail_direct(
        request, charge=charge, organization=organization, strength=STRONG)


def fail_provider(request, charge=None, organization=None, strength=NORMAL):
    """
    Returns False if the request authenticated ``User``
    is a contributor (or manager) for the ``Organization`` associated to
    the request itself or a contributor (or manager) to a provider for
    the ``Organization`` associated to the request.

    When *strength* is NORMAL, managers can issue all types of requests
    (GET, POST, etc.) while contributors are restricted to GET requests.

    .. image:: perms-contrib-subscribes.*
    """
    if charge and not isinstance(charge, Charge):
        charge = get_object_or_404(Charge, processor_key=charge)
        organization = charge.customer
    elif organization and not isinstance(organization, Organization):
        organization = get_object_or_404(Organization, slug=organization)
    candidates = [get_broker()]
    if organization:
        candidates = ([organization]
            + list(Organization.objects.providers_to(organization))
            + candidates)
    return not _has_valid_access(request, candidates, strength=strength)


def fail_provider_weak(request, charge=None, organization=None):
    """
    Returns False if the request authenticated ``User``
    is a contributor (or manager) for the ``Organization`` associated to
    the request itself or a contributor (or manager) to a provider for
    the ``Organization`` associated to the request.

    Both managers and contributors can issue all types of requests
    (GET, POST, etc.).
    """
    return fail_provider(
        request, charge=charge, organization=organization, strength=WEAK)


def fail_provider_strong(request, charge=None, organization=None):
    """
    Returns False if the request authenticated ``User``
    is a manager for the ``Organization`` associated to the request itself
    or a manager to a provider for the ``Organization`` associated
    to the request.
    """
    return fail_provider(
        request, charge=charge, organization=organization, strength=STRONG)


def fail_provider_only(request,
                       charge=None, organization=None, strength=NORMAL):
    """
    Returns False if the request authenticated ``User``
    is a contributor (or manager) for a provider to the ``Organization``
    associated to the request.

    When *strength* is NORMAL, managers can issue all types of requests
    (GET, POST, etc.) while contributors are restricted to GET requests.

    .. image:: perms-contrib-provider-only.*
    """
    if charge:
        charge = get_object_or_404(Charge, processor_key=charge)
        organization = charge.customer
    elif organization:
        organization = get_object_or_404(Organization, slug=organization)
    candidates = [get_broker()]
    if organization:
        candidates = (list(Organization.objects.providers_to(organization))
            + candidates)
    return not _has_valid_access(request, candidates, strength=strength)


def fail_provider_only_weak(request, charge=None, organization=None):
    """
    Returns False if the request authenticated ``User``
    is a contributor (or manager) for a provider to the ``Organization``
    associated to the request.

    Both managers and contributors can issue all types of requests
    (GET, POST, etc.).
    """
    return fail_provider_only(
        request, charge=charge, organization=organization, strength=WEAK)


def fail_provider_only_strong(request, charge=None, organization=None):
    """
    Returns False if the request authenticated ``User``
    is a manager for a provider to the ``Organization`` associated
    to the request.
    """
    return fail_provider_only(
        request, charge=charge, organization=organization, strength=STRONG)


def fail_self_provider(request, user=None, strength=NORMAL):
    """
    Returns True if the request authenticated ``User``
    is the user associated to the URL.
    Authenticated users that can also access the URL through this decorator
    are contributors (or managers) for any ``Organization`` associated
    with the user served by the URL (the accessed user is a direct contributor
    or manager of the organization) and transitively contributors (or managers)
    for any provider to one of these direct organizations.

    When *strength* is NORMAL, managers can issue all types of requests
    (GET, POST, etc.) while contributors are restricted to GET requests.

    .. image:: perms-self-contrib-subscribes.*
    """
    if request.user.username != user:
        # Organization that are managed by both users
        directs = Organization.objects.accessible_by(user)
        providers = Organization.objects.providers(
            Subscription.objects.filter(organization__in=directs))
        candidates = list(directs) + list(providers) + [get_broker()]
        return not _has_valid_access(request, candidates, strength)
    return False


def fail_self_provider_weak(request, user=None):
    """
    Returns False if the request authenticated ``User``
    is the user associated to the URL.
    Authenticated users that can also access the URL through this decorator
    are contributors (or managers) for any ``Organization`` associated
    with the user served by the URL (the accessed user is a direct contributor
    or manager of the organization) and transitively contributors (or managers)
    for any provider to one of these direct organizations.

    Both managers and contributors can issue all types of requests
    (GET, POST, etc.).
    """
    return fail_self_provider(request, user=user, strength=WEAK)


def fail_self_provider_strong(request, user=None):
    """
    Returns False if the request authenticated ``User``
    is the user associated to the URL.
    Authenticated users that can also access the URL through this decorator
    are managers for any ``Organization`` associated with the user served
    by the URL (the accessed user is a direct manager of the organization
    and transitively managers for any provider to one of these direct
    organizations.
    """
    return fail_self_provider(request, user=user, strength=STRONG)


def requires_authenticated(function=None,
                           redirect_field_name=REDIRECT_FIELD_NAME):
    """
    Decorator for views that checks that the user is authenticated.

    ``django.contrib.auth.decorators.login_required`` will automatically
    redirect to the login page. We want to raise a ``PermissionDenied``
    instead when Content-Type is showing we are dealing with an API request.
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            redirect = fail_authenticated(request)
            if redirect:
                accept_content_type = request.META.get('HTTP_ACCEPT',
                    request.META.get('CONTENT_TYPE', ''))
                if (not 'application/json' in accept_content_type.lower()
                    and isinstance(redirect, basestring)):
                    # If the client accepts 'application/json' regardless
                    # of preference order, we will return a 403. Otherwise
                    # we will reply with a redirect to the login page.
                    return _insert_url(request, redirect_field_name, redirect)
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def requires_agreement(function=None,
                       agreement=settings.TERMS_OF_USE,
                       redirect_field_name=REDIRECT_FIELD_NAME):
    """
    Decorator for views that checks that the user has signed a particular
    legal agreement, redirecting to the agreement signature or log-in page
    if necessary.
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            redirect = fail_agreement(request, agreement=agreement)
            if redirect:
                return _insert_url(request, redirect_field_name, redirect)
            return view_func(request, *args, **kwargs)
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def requires_paid_subscription(function=None,
                              organization_kwarg_slug='organization',
                              plan_kwarg_slug='subscribed_plan',
                              redirect_field_name=REDIRECT_FIELD_NAME,
                              strength=NORMAL):
    """
    Decorator that checks a specified subscription is paid. It redirects to an
    appropriate page when this is not the case:

    - Payment page when no charge is associated to the subscription,
    - Update Credit Card page when ``charge.status`` is ``failed``,
    - Waiting page when ``charge.status`` is ``in-progress``.
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            subscriber = get_object_or_404(
                Organization, slug=kwargs.get(organization_kwarg_slug, None))
            if fail_provider(request,
                             organization=subscriber, strength=strength):
                raise PermissionDenied("%(user)s is neither a manager '\
' of %(organization)s nor a manager of one of %(organization)s providers."
                % {'user': request.user, 'organization': subscriber})
            redirect = fail_paid_subscription(request, organization=subscriber,
                plan=kwargs.get(plan_kwarg_slug, None))
            if redirect:
                # Note: I couldn't figure out why passing kwargs
                # stopped working.
                return _insert_url(request, redirect_field_name, redirect)
            return view_func(request, *args, **kwargs)
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def requires_direct(function=None, strength=NORMAL):
    """
    Decorator for views that checks that the request authenticated ``User``
    is a direct contributor (or manager) for the ``Organization`` associated
    to the request.

    Managers can issue all types of requests (GET, POST, etc.) while
    contributors are restricted to GET requests.

    .. image:: perms-contrib.*
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            organization = kwargs.get('organization', None)
            if fail_direct(request, charge=kwargs.get('charge', None),
                           organization=organization,
                           strength=strength):
                raise PermissionDenied("%(user)s is not a direct manager '\
' of %(organization)s." % {'user': request.user, 'organization': organization})
            return view_func(request, *args, **kwargs)
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def requires_direct_weak(function=None):
    """
    Decorator for views that checks that the request authenticated ``User``
    is a direct contributor (or manager) for the ``Organization`` associated
    to the request.

    Both managers and contributors can issue all types of requests
    (GET, POST, etc.).
    """
    return requires_direct(function, strength=WEAK)


def requires_direct_strong(function=None):
    """
    Decorator for views that checks that the request authenticated ``User``
    is a direct manager for the ``Organization`` associated to the request.
    """
    return requires_direct(function, strength=STRONG)


def requires_provider(function=None, strength=NORMAL):
    """
    Decorator for views that checks that the request authenticated ``User``
    is a contributor (or manager) for the ``Organization`` associated to
    the request itself or a contributor (or manager) to a provider for
    the ``Organization`` associated to the request.

    When *strength* is NORMAL, managers can issue all types of requests
    (GET, POST, etc.) while contributors are restricted to GET requests.

    .. image:: perms-contrib-subscribes.*
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            if fail_provider(request, charge=kwargs.get('charge', None),
                             organization=kwargs.get('organization', None),
                             strength=strength):
                raise PermissionDenied("%(auth)s is neither a manager "\
" for %(slug)s nor a manager of one of %(slug)s providers." % {
    'auth': request.user,
    'slug': kwargs.get('charge', kwargs.get('organization', None))})
            return view_func(request, *args, **kwargs)
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def requires_provider_weak(function=None):
    """
    Decorator for views that checks that the request authenticated ``User``
    is a contributor (or manager) for the ``Organization`` associated to
    the request itself or a contributor (or manager) to a provider for
    the ``Organization`` associated to the request.

    Both managers and contributors can issue all types of requests
    (GET, POST, etc.).
    """
    return requires_provider(function, strength=WEAK)


def requires_provider_strong(function=None):
    """
    Decorator for views that checks that the request authenticated ``User``
    is a manager for the ``Organization`` associated to the request itself
    or a manager to a provider for the ``Organization`` associated
    to the request.
    """
    return requires_provider(function, strength=STRONG)


def requires_provider_only(function=None, strength=NORMAL):
    """
    Decorator for views that checks that the request authenticated ``User``
    is a contributor (or manager) for a provider to the ``Organization``
    associated to the request.

    When *strength* is NORMAL, managers can issue all types of requests
    (GET, POST, etc.) while contributors are restricted to GET requests.

    .. image:: perms-contrib-provider-only.*
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            if fail_provider_only(request, charge=kwargs.get('charge', None),
                             organization=kwargs.get('organization', None),
                             strength=strength):
                raise PermissionDenied("%(auth)s has no direct relation to"\
" a provider for %(slug)s." % {'auth': request.user,
        'slug': kwargs.get('charge', kwargs.get('organization', None))})
            return view_func(request, *args, **kwargs)
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def requires_provider_only_weak(function=None):
    """
    Decorator for views that checks that the request authenticated ``User``
    is a contributor (or manager) for a provider to the ``Organization``
    associated to the request.

    Both managers and contributors can issue all types of requests
    (GET, POST, etc.).
    """
    return requires_provider_only(function, strength=WEAK)


def requires_provider_only_strong(function=None):
    """
    Decorator for views that checks that the request authenticated ``User``
    is a manager for a provider to the ``Organization`` associated
    to the request.
    """
    return requires_provider_only(function, strength=STRONG)


def requires_self_provider(function=None, strength=NORMAL):
    """
    Decorator for views that checks that the request authenticated ``User``
    is the user associated to the URL.
    Authenticated users that can also access the URL through this decorator
    are contributors (or managers) for any ``Organization`` associated
    with the user served by the URL (the accessed user is a direct contributor
    or manager of the organization) and transitively contributors (or managers)
    for any provider to one of these direct organizations.

    When *strength* is NORMAL, managers can issue all types of requests
    (GET, POST, etc.) while contributors are restricted to GET requests.

    .. image:: perms-self-contrib-subscribes.*
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            if fail_self_provider(
                    request, user=kwargs.get('user', None), strength=strength):
                raise PermissionDenied("%(auth)s has neither a direct"\
" relation to an organization connected to %(user)s nor a connection to one"\
"of the providers to such organization." % {
    'auth': request.user, 'user': kwargs.get('user', None)})
            return view_func(request, *args, **kwargs)
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def requires_self_provider_weak(function=None):
    """
    Decorator for views that checks that the request authenticated ``User``
    is the user associated to the URL.
    Authenticated users that can also access the URL through this decorator
    are contributors (or managers) for any ``Organization`` associated
    with the user served by the URL (the accessed user is a direct contributor
    or manager of the organization) and transitively contributors (or managers)
    for any provider to one of these direct organizations.

    Both managers and contributors can issue all types of requests
    (GET, POST, etc.).
    """
    return requires_self_provider(function, strength=WEAK)


def requires_self_provider_strong(function=None):
    """
    Decorator for views that checks that the request authenticated ``User``
    is the user associated to the URL.
    Authenticated users that can also access the URL through this decorator
    are managers for any ``Organization`` associated with the user served
    by the URL (the accessed user is a direct manager of the organization
    and transitively managers for any provider to one of these direct
    organizations.
    """
    return requires_self_provider(function, strength=STRONG)


