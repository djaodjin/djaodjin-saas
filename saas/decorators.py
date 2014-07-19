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
We used to decorate the saas views with the "appropriate" decorators
except in many projects appropriate had a different meaning.

It turns out that the access control logic is better left to be configured
in the site URLConf through extensions like django-urldecorators:

    https://github.com/mila/django-urldecorators.

This is not only more flexible but also make security audits a lot easier.
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

from saas.models import Charge, Organization, Plan, Signature, Subscription
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


def _contributor_readonly(request, candidates):
    """
    Returns a tuple made of two list of ``Organization`` from *candidates*.
    """
    if request.method == "GET":
        managed, contributed = _valid_contributor(request.user, candidates)
    else:
        contributed = []
        managed = _valid_manager(request.user, candidates)
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
            elif kwargs.has_key('charge'):
                charge = get_object_or_404(
                    Charge, processor_id=kwargs.get('charge'))
                organization = charge.customer
            elif kwargs.has_key('organization'):
                organization = get_object_or_404(Organization,
                    slug=kwargs.get('organization'))
            if _contributor_readonly(request, [organization]):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def requires_manager_or_provider(function=None):
    """
    Validates the user is a manager for the organization or a manager
    for the provider's organization.
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            organization = get_object_or_404(Organization,
                slug=kwargs.get('organization'))
            if _contributor_readonly(request, [organization]
                + list(Organization.objects.providers_to(organization))):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("%(user)s is neither a manager '\
' of %(organization)s nor a manager of one of %(organization)s providers."
                        % {'user': request.user, 'organization': organization})
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def requires_paid_subscription(function=None,
                              organization_kwarg_slug='organization',
                              plan_kwarg_slug='subscribed_plan',
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
            if kwargs.has_key(organization_kwarg_slug):
                subscribers = _valid_manager(
                    request.user, Organization.objects.filter(
                        slug=kwargs.get(organization_kwarg_slug)))
                if len(subscribers) > 0:
                    subscriber = subscribers[0]
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


def requires_self_manager_provider(function=None):
    """
    Decorator that checks that the user is either herself
    or a manager for an organization providing services to
    an organization the user is involved with.
    """
    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated():
                raise PermissionDenied
            if request.user.username != kwargs.get('user'):
                # Organization that are managed by both users
                managed = Organization.objects.filter(
                    managers__username=kwargs.get('user'))
                providers = Organization.objects.providers(
                    Subscription.objects.filter(organization__in=managed))
                if not _contributor_readonly(request,
                                             list(managed) + list(providers)):
                    raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator
