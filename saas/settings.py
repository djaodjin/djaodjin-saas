# Copyright (c) 2021, DjaoDjin inc.
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

The ``Organization`` broker manages the StripeConnect client account.

========================  ================= ===========
Name                      Default           Description
========================  ================= ===========
BROKER.GET_INSTANCE       basename(BASE_DIR)Slug for the ``Organization`` broker
                                            or callable that returns the
                                            ``Organization`` broker
                                            (useful for composition of Django
                                            apps).
BROKER.IS_INSTANCE_CALLABLE None            Function that will return `True`
                                            if the provider argument is the
                                            broker. If `None` we will compare
                                            provider with the instance returned
                                            by `BROKER.GET_INSTANCE`.
BYPASS_PERMISSION_CHECK    False            Skip all permission checks
BYPASS_PROCESSOR_AUTH      False            Do not check the auth token against
                                            the processor to set processor keys
                                            (useful to test StripeConnect).
DISABLE_UPDATES           False             When `True`, modifications are not
                                            allowed.
EXTRA_MIXIN               object            Class to to inject into the parents
                                            of the Mixin hierarchy.
                                            (useful for composition of Django
                                            apps)
ORGANIZATION_MODEL        saas.Organization Replace the ``Organization`` model
                                            (useful for composition of Django
                                            apps)
PAGE_SIZE                 25                Maximum number of objects to return
                                            per API calls.
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
TERMS_OF_USE             'terms-of-use'     slug for the ``Agreement`` stating
                                            ther Terms of Use of the site.
========================  ================= ===========
"""
import os

from django.conf import settings

_SETTINGS = {
    'BROKER': {
        'GET_INSTANCE': os.path.basename(
            getattr(settings, 'BASE_DIR', "broker")),
        'IS_INSTANCE_CALLABLE': None,
        'BUILD_ABSOLUTE_URI_CALLABLE': None,
        'FEE_PERCENTAGE': 0
    },
    'BYPASS_IMPLICIT_GRANT': {},
    'BYPASS_PERMISSION_CHECK': False,
    # Do not check the auth token against the processor to set processor keys.
    # (useful while testing).
    'BYPASS_PROCESSOR_AUTH': False,
    'DEFAULT_UNIT': 'usd',
    'DISABLE_UPDATES': False,
    'EXPIRE_NOTICE_DAYS': [15],
    'EXTRA_MIXIN': object,
    'EXTRA_FIELD': None,
    'INACTIVITY_DAYS': 90,
    'MAX_RENEWAL_ATTEMPTS': 3,
    'MAX_TYPEAHEAD_CANDIDATES': 5,
    'ORGANIZATION_MODEL': getattr(settings, 'SAAS_ORGANIZATION_MODEL',
        'saas.Organization'),
    'PAGE_SIZE': 25,
    'PICTURE_STORAGE_CALLABLE': None,
    'PROCESSOR': {
        'BACKEND': 'saas.backends.stripe_processor.StripeBackend',
        'CLIENT_ID': None,
        'CONNECT_STATE_CALLABLE': None,
        'CONNECT_CALLBACK_URL': None,
        'FALLBACK': False,
        'INSTANCE_PK': 1,
        'MODE': 0,
        'PRIV_KEY': None,
        'PUB_KEY': None,
        'REDIRECT_CALLABLE': None,
        'USE_STRIPE_V3': False,
        'WEBHOOK_URL': 'stripe/postevent',
        'WEBHOOK_SECRET': None,
    },
    'PROCESSOR_BACKEND_CALLABLE': None,
    'ROLE_RELATION': getattr(settings, 'SAAS_ROLE_MODEL', 'saas.Role'),
    'ROLE_SERIALIZER': 'saas.api.serializers.RoleSerializer',
    'USER_SERIALIZER': 'saas.api.serializers_overrides.UserSerializer',
    'SEARCH_FIELDS_PARAM': 'q_f',
    'TERMS_OF_USE': 'terms-of-use',
}
_SETTINGS.update(getattr(settings, 'SAAS', {}))


SLUG_RE = r'[a-zA-Z0-9_\-\+\.]+'
ACCT_REGEX = SLUG_RE
MAYBE_EMAIL_REGEX = r'[a-zA-Z0-9_\-\+\.\@]+'
SELECTOR_RE = r'[a-zA-Z0-9_\-\:]+'
VERIFICATION_KEY_RE = r'[a-f0-9]{40}'
AUTH_USER_MODEL = getattr(
    settings, 'AUTH_USER_MODEL', 'django.contrib.auth.models.User')

BROKER_CALLABLE = _SETTINGS.get('BROKER').get('GET_INSTANCE', None)
BROKER_FEE_PERCENTAGE = _SETTINGS.get('BROKER').get('FEE_PERCENTAGE', 0)
BUILD_ABSOLUTE_URI_CALLABLE = _SETTINGS.get('BROKER').get(
    'BUILD_ABSOLUTE_URI_CALLABLE')
BYPASS_IMPLICIT_GRANT = _SETTINGS.get('BYPASS_IMPLICIT_GRANT')
BYPASS_PROCESSOR_AUTH = _SETTINGS.get('BYPASS_PROCESSOR_AUTH')
CREDIT_ON_CREATE = _SETTINGS.get('CREDIT_ON_CREATE')
DEFAULT_UNIT = _SETTINGS.get('DEFAULT_UNIT')
DISABLE_UPDATES = _SETTINGS.get('DISABLE_UPDATES')
EXPIRE_NOTICE_DAYS = _SETTINGS.get('EXPIRE_NOTICE_DAYS')
EXTRA_MIXIN = _SETTINGS.get('EXTRA_MIXIN')
INACTIVITY_DAYS = _SETTINGS.get('INACTIVITY_DAYS')
IS_BROKER_CALLABLE = _SETTINGS.get('BROKER').get('IS_INSTANCE_CALLABLE', None)
MAX_RENEWAL_ATTEMPTS = _SETTINGS.get('MAX_RENEWAL_ATTEMPTS')
MAX_TYPEAHEAD_CANDIDATES = _SETTINGS.get('MAX_TYPEAHEAD_CANDIDATES')
ORGANIZATION_MODEL = _SETTINGS.get('ORGANIZATION_MODEL')
PAGE_SIZE = _SETTINGS.get('PAGE_SIZE')
PROCESSOR = _SETTINGS.get('PROCESSOR')
PROCESSOR_BACKEND_CALLABLE = _SETTINGS.get('PROCESSOR_BACKEND_CALLABLE')
PROCESSOR_FALLBACK = PROCESSOR.get('FALLBACK', [])
PROCESSOR_ID = PROCESSOR.get('INSTANCE_PK', 1)
PROCESSOR_HOOK_URL = PROCESSOR.get('WEBHOOK_URL', 'stripe/postevent')
PROCESSOR_HOOK_SECRET = PROCESSOR.get('WEBHOOK_SECRET')
ROLE_RELATION = _SETTINGS.get('ROLE_RELATION')
ROLE_SERIALIZER = _SETTINGS.get('ROLE_SERIALIZER')
USER_SERIALIZER = _SETTINGS.get('USER_SERIALIZER')
SEARCH_FIELDS_PARAM = _SETTINGS.get('SEARCH_FIELDS_PARAM')
TERMS_OF_USE = _SETTINGS.get('TERMS_OF_USE')

# BE EXTRA CAREFUL! This variable is used to bypass PermissionDenied
# exceptions. It is solely intended as a debug flexibility nob.
BYPASS_PERMISSION_CHECK = _SETTINGS.get('BYPASS_PERMISSION_CHECK')
PICTURE_STORAGE_CALLABLE = _SETTINGS.get('PICTURE_STORAGE_CALLABLE')
EXTRA_FIELD = _SETTINGS.get('EXTRA_FIELD')

LOGIN_URL = getattr(settings, 'LOGIN_URL')
TIME_ZONE = getattr(settings, 'TIME_ZONE')

CONTRIBUTOR = 'contributor'
MANAGER = 'manager'
PROFILE_URL_KWARG = 'organization'
#PROFILE_URL_KWARG = 'profile'
