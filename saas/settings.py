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
"""
from django.conf import settings

_SETTINGS = {
    # Organization for which pass_contributor is always True.
    'BYPASS_CONTRIBUTOR_CHECK': [],
    'CREDIT_ON_CREATE': 1000,
    'EXTRA_MIXIN': object,
    'ORGANIZATION_MODEL': 'saas.Organization',
    'PAGE_SIZE': 25,
    'PLATFORM': getattr(settings, 'APP_NAME', None),
    'PROCESSOR_ID': 1,
    'PROCESSOR_BACKEND_CALLABLE': None,
    'PROCESSOR_HOOK_URL': 'api/postevent',
    'PROCESSOR_REDIRECT_CALLABLE': None,
    'PROVIDER_CALLABLE': None,
    'PROVIDER_SITE_CALLABLE': None,
    'ROLE_RELATION': 'saas.Role',
    'SKIP_PERMISSION_CHECK': False,
    'STRIPE_MODE': 0,
    'STRIPE_CLIENT_ID': None,
    'STRIPE_PRIV_KEY': None,
    'STRIPE_PUB_KEY': None,
    'TERMS_OF_USE': 'terms-of-use',
}
_SETTINGS.update(getattr(settings, 'SAAS', {}))


ACCT_REGEX = r'[a-zA-Z0-9_\-]+'
SELECTOR_RE = r'[a-zA-Z0-9_\-\:]+'
AUTH_USER_MODEL = getattr(
    settings, 'AUTH_USER_MODEL', 'django.contrib.auth.models.User')

BYPASS_CONTRIBUTOR_CHECK = _SETTINGS.get('BYPASS_CONTRIBUTOR_CHECK')
CREDIT_ON_CREATE = _SETTINGS.get('CREDIT_ON_CREATE')
EXTRA_MIXIN = _SETTINGS.get('EXTRA_MIXIN')
ORGANIZATION_MODEL = _SETTINGS.get('ORGANIZATION_MODEL')
PAGE_SIZE = _SETTINGS.get('PAGE_SIZE')
PLATFORM = _SETTINGS.get('PLATFORM')
PROCESSOR_BACKEND_CALLABLE = _SETTINGS.get('PROCESSOR_BACKEND_CALLABLE')
PROCESSOR_HOOK_URL = _SETTINGS.get('PROCESSOR_HOOK_URL')
PROCESSOR_REDIRECT_CALLABLE = _SETTINGS.get('PROCESSOR_REDIRECT_CALLABLE')
PROVIDER_CALLABLE = _SETTINGS.get('PROVIDER_CALLABLE')
PROVIDER_SITE_CALLABLE = _SETTINGS.get('PROVIDER_SITE_CALLABLE')
PROCESSOR_ID = _SETTINGS.get('PROCESSOR_ID')
ROLE_RELATION = _SETTINGS.get('ROLE_RELATION')
STRIPE_MODE = _SETTINGS.get('STRIPE_MODE')
STRIPE_CLIENT_ID = _SETTINGS.get('STRIPE_CLIENT_ID')
STRIPE_PRIV_KEY = _SETTINGS.get('STRIPE_PRIV_KEY')
STRIPE_PUB_KEY = _SETTINGS.get('STRIPE_PUB_KEY')
TERMS_OF_USE = _SETTINGS.get('TERMS_OF_USE')

# BE EXTRA CAREFUL! This variable is used to bypass PermissionDenied
# exceptions. It is solely intended as a debug flexibility nob.
SKIP_PERMISSION_CHECK = _SETTINGS.get('SKIP_PERMISSION_CHECK')

LOGIN_URL = getattr(settings, 'LOGIN_URL')
MANAGER = 'manager'
CONTRIBUTOR = 'contributor'
