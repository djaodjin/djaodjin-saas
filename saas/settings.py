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
Convenience module for access of saas application settings, which enforces
default settings when the main settings module does not contain
the appropriate settings.

========================  ================= ===========
Name                      Default           Description
========================  ================= ===========
BROKER_CALLABLE            None             Optional function that returns
                                            the broker ``Organization``
                                            (useful for composition of Django
                                            apps).
BYPASS_CONTRIBUTOR_CHECK    []              List of ``Organization`` for which
                                            ``_valid_contributor`` is always
                                            True.
BYPASS_PROCESSOR_AUTH      False            Do not check the auth token against
                                            the processor to set processor keys
                                            (useful to test StripeConnect).
EXTRA_MIXIN               object            Class to to inject into the parents
                                            of the Mixin hierarchy.
                                            (useful for composition of Django
                                            apps)
ORGANIZATION_MODEL        saas.Organization Replace the ``Organization`` model
                                            (useful for composition of Django
                                            apps)
PAGE_SIZE                 25                Maximum number of objects to return
                                            per API calls.
PLATFORM                  None              slug of Organization managing the
                                            StripeConnect client account.
PROCESSOR                :doc:`Stripe backend<backends>`
PROCESSOR_ID             1                  pk of the processor ``Organization``
PROCESSOR_BACKEND_CALLABLE None             Optional function that returns
                                            the processor backend
                                            (useful for composition of Django
                                            apps).
PROVIDER_SITE_CALLABLE   None               Optional function that returns
                                            an object with a ``domain``
                                            field that is used to generate
                                            fully qualified URLs.
                                            (useful for composition of Django
                                            apps)
ROLE_RELATION            saas.Role          Replace the ``Role`` model
                                            (useful for composition of Django
                                            apps)
SKIP_PERMISSION_CHECK    False              Skip all permission checks
TERMS_OF_USE             'terms-of-use'     slug for the ``Agreement`` stating
                                            ther Terms of Use of the site.
========================  ================= ===========
"""
from django.conf import settings

_SETTINGS = {
    'BYPASS_CONTRIBUTOR_CHECK': [],
    # Do not check the auth token against the processor to set processor keys.
    # (useful while testing).
    'BYPASS_PROCESSOR_AUTH': False,
    'EXTRA_MIXIN': object,
    'ORGANIZATION_MODEL': 'saas.Organization',
    'PAGE_SIZE': 25,
    'PLATFORM': getattr(settings, 'APP_NAME', None),
    'PROCESSOR': {
        'BACKEND': 'saas.backends.stripe_processor.StripeBackend',
        'PRIV_KEY': None,
        'PUB_KEY': None,
        'CLIENT_ID': None,
        'MODE': 0,
        'WEBHOOK_URL': 'api/postevent',
        'REDIRECT_CALLABLE': None
    },
    'PROCESSOR_ID': 1,
    'PROCESSOR_BACKEND_CALLABLE': None,
    'PROCESSOR_HOOK_URL': 'api/postevent',
    'PROCESSOR_REDIRECT_CALLABLE': None,
    'BROKER_CALLABLE': None,
    'PROVIDER_SITE_CALLABLE': None,
    'ROLE_RELATION': 'saas.Role',
    'SKIP_PERMISSION_CHECK': False,
    'TERMS_OF_USE': 'terms-of-use',
}
_SETTINGS.update(getattr(settings, 'SAAS', {}))


ACCT_REGEX = r'[a-zA-Z0-9_\-\+\.]+'
SELECTOR_RE = r'[a-zA-Z0-9_\-\:]+'
AUTH_USER_MODEL = getattr(
    settings, 'AUTH_USER_MODEL', 'django.contrib.auth.models.User')

BYPASS_CONTRIBUTOR_CHECK = _SETTINGS.get('BYPASS_CONTRIBUTOR_CHECK')
BYPASS_PROCESSOR_AUTH = _SETTINGS.get('BYPASS_PROCESSOR_AUTH')
CREDIT_ON_CREATE = _SETTINGS.get('CREDIT_ON_CREATE')
EXTRA_MIXIN = _SETTINGS.get('EXTRA_MIXIN')
ORGANIZATION_MODEL = _SETTINGS.get('ORGANIZATION_MODEL')
PAGE_SIZE = _SETTINGS.get('PAGE_SIZE')
PLATFORM = _SETTINGS.get('PLATFORM')
PROCESSOR = _SETTINGS.get('PROCESSOR')
PROCESSOR_BACKEND_CALLABLE = _SETTINGS.get('PROCESSOR_BACKEND_CALLABLE')
PROCESSOR_ID = _SETTINGS.get('PROCESSOR_ID')
PROCESSOR_HOOK_URL = _SETTINGS.get('PROCESSOR').get(
    'WEBHOOK_URL', 'api/postevent')
BROKER_CALLABLE = _SETTINGS.get('BROKER_CALLABLE')
PROVIDER_SITE_CALLABLE = _SETTINGS.get('PROVIDER_SITE_CALLABLE')
ROLE_RELATION = _SETTINGS.get('ROLE_RELATION')
TERMS_OF_USE = _SETTINGS.get('TERMS_OF_USE')

# BE EXTRA CAREFUL! This variable is used to bypass PermissionDenied
# exceptions. It is solely intended as a debug flexibility nob.
SKIP_PERMISSION_CHECK = _SETTINGS.get('SKIP_PERMISSION_CHECK')

LOGIN_URL = getattr(settings, 'LOGIN_URL')
MANAGER = 'manager'
CONTRIBUTOR = 'contributor'
