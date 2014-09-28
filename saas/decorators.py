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
The access control logic is best configured in the site URLConf through
extensions like `django-urldecorators`_. This is not only more flexible but
also make security audits a lot easier.

.. _django-urldecorators: https://github.com/mila/django-urldecorators
"""

import logging, urlparse

from functools import wraps
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import available_attrs

from saas.models import (Charge, Organization, Plan, Signature, Subscription,
    get_current_provider)
from saas.settings import SKIP_PERMISSION_CHECK

LOGGER = logging.getLogger(__name__)


def _valid_manager(user, candidates):
    """
    Returns the subset of a queryset of ``Organization``, *candidates*
    which have *user* as a manager.
    """
    results = []
    if SKIP_PERMISSION_CHECK:
        if user:
            username = user.username
        else:
            username = '(none)'
        LOGGER.warning("Skip permission check for %s on organizations %s",
                       username, candidates)
        return candidates
    if user and user.is_authenticated():
        try:
            return candidates.filter(managers__id=user.id)
        except AttributeError:
            for candidate in candidates:
                if candidate.managers.filter(id=user.id).exists():
                    results += [candidate]
    return results


def _valid_contributor(user, candidates):
    """
    Returns a tuple made of two list of ``Organization`` from *candidates*.
    The first element contains organizations which have *user*
    as a manager. The second element contains organizations which have *user*
    as a contributor.
    """
    contributed = []
    managed = _valid_manager(user, candidates)
    if user and user.is_authenticated():
        try:
            contributed = candidates.exclude(managed).filter(
                contributors__id=user.id)
        except AttributeError:
            for candidate in candidates:
                if (not candidate in managed
                    and candidate.contributors.filter(id=user.id).exists()):
                    contributed += [candidate]
    return (managed, contributed)


def _valid_contributor_readonly(request, candidates):
    """
    Returns a tuple made of two list of ``Organization`` from *candidates*.
    """
    if request.method == "GET":
        managed, contributed = _valid_contributor(request.user, candidates)
    else:
        contributed = []
        managed = _valid_manager(request.user, candidates)
    return managed, contributed


def _contributor_readonly(request, candidates):
    """
    Returns True if any candidate is accessible to the request user.
    """
    managed, contributed = _valid_contributor_readonly(request, candidates)
    return len(managed + contributed) > 0


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


def requires_paid_subscription(function=None,
                              organization_kwarg_slug='organization',
                              plan_kwarg_slug='subscribed_plan',
                              redirect_field_name=REDIRECT_FIELD_NAME):
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
            subscriber = None
            if kwargs.has_key(organization_kwarg_slug):
                subscriber = get_object_or_404(Organization,
                    slug=kwargs.get(organization_kwarg_slug))
                if not _contributor_readonly(request, [subscriber]
                    + list(Organization.objects.providers_to(subscriber))):
                    raise PermissionDenied("%(user)s is neither a manager '\
' of %(organization)s nor a manager of one of %(organization)s providers."
                        % {'user': request.user, 'organization': subscriber})
            plan = None
            if kwargs.has_key(plan_kwarg_slug):
                plan = get_object_or_404(
                    Plan, slug=kwargs.get(plan_kwarg_slug))
            if subscriber and plan:
                subscription = get_object_or_404(Subscription,
                    organization=subscriber, plan=plan)
                if subscription.is_locked:
                    return _insert_url(request, redirect_field_name,
                        reverse('saas_organization_balance',
                            kwargs={'organization': subscriber,
                                    'subscribed_plan': plan}))
                return view_func(request, *args, **kwargs)
            raise Http404

        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def requires_direct(function=None):
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
            organization = None
            if kwargs.has_key('charge'):
                charge = get_object_or_404(
                    Charge, processor_id=kwargs.get('charge'))
                organization = charge.customer
            elif kwargs.has_key('organization'):
                organization = get_object_or_404(Organization,
                    slug=kwargs.get('organization'))
            else:
                organization = get_current_provider()
            if organization and _contributor_readonly(request, [organization]):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def requires_provider(function=None):
    """
    Decorator for views that checks that the request authenticated ``User``
    is a contributor (or manager) for the ``Organization`` associated to
    the request itself or a contributor (or manager) to a provider for
    the ``Organization`` associated to the request.

    Managers can issue all types of requests (GET, POST, etc.) while
    contributors are restricted to GET requests.

    .. image:: perms-contrib-subscribes.*
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            organization = None
            if kwargs.has_key('charge'):
                charge = get_object_or_404(
                    Charge, processor_id=kwargs.get('charge'))
                organization = charge.customer
            elif kwargs.has_key('organization'):
                organization = get_object_or_404(Organization,
                    slug=kwargs.get('organization'))
            if organization and _contributor_readonly(request, [organization]
                + list(Organization.objects.providers_to(organization))):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("%(auth)s is neither a manager "\
" of %(organization)s nor a manager of one of %(organization)s providers."
                        % {'auth': request.user, 'organization': organization})
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def requires_provider_only(function=None):
    """
    Decorator for views that checks that the request authenticated ``User``
    is a contributor (or manager) for a provider to the ``Organization``
    associated to the request.

    Managers can issue all types of requests (GET, POST, etc.) while
    contributors are restricted to GET requests.

    .. image:: perms-contrib-provider-only.*
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            organization = None
            if kwargs.has_key('charge'):
                charge = get_object_or_404(
                    Charge, processor_id=kwargs.get('charge'))
                organization = charge.customer
            elif kwargs.has_key('organization'):
                organization = get_object_or_404(Organization,
                    slug=kwargs.get('organization'))
            if organization and _contributor_readonly(request,
                list(Organization.objects.providers_to(organization))):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("%(auth)s has no direct relation to"\
" a provider of %(organization)s."
                        % {'auth': request.user, 'organization': organization})
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def requires_self_provider(function=None):
    """
    Decorator for views that checks that the request authenticated ``User``
    is the user associated to the URL.
    Authenticated users that can also access the URL through this decorator
    are contributors (or managers) for any ``Organization`` associated
    with the user served by the URL (the accessed user is a direct contributor
    or manager of the organization) and transitively contributors (or managers)
    for any provider to one of these direct organizations.

    Managers can issue all types of requests (GET, POST, etc.) while
    contributors are restricted to GET requests.

    .. image:: perms-self-contrib-subscribes.*
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated():
                raise PermissionDenied
            if request.user.username != kwargs.get('user'):
                # Organization that are managed by both users
                directs = Organization.objects.accessible_by(kwargs.get('user'))
                providers = Organization.objects.providers(
                    Subscription.objects.filter(organization__in=directs))
                if not _contributor_readonly(request,
                                             list(directs) + list(providers)):
                    raise PermissionDenied("%(auth)s has neither a direct"\
" relation to an organization connected to %(user)s nor a connection to one"\
"of the providers to such organization."
                        % {'auth': request.user, 'user': kwargs.get('user')})
            return view_func(request, *args, **kwargs)
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator
