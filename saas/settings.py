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
Convenience module for access of saas application settings, which enforces
default settings when the main settings module does not contain
the appropriate settings.
"""
from django.conf import settings

_SETTINGS = {
    'CREDIT_ON_CREATE': 1000,
    'CONTRIBUTOR_RELATION': 'saas.Organization_Contributors',
    'MANAGER_RELATION': 'saas.Organization_Managers',
    'PROCESSOR_HOOK_URL': 'postevent',
    'PROVIDER_CALLABLE': None,
    'SKIP_PERMISSION_CHECK': False,
    'PROVIDER_ID': getattr(settings, 'SITE_ID', 1),
    'PROCESSOR_ID': 1,
}
_SETTINGS.update(getattr(settings, 'SAAS', {}))


ACCT_REGEX = r'[a-zA-Z0-9_\-]+'
AUTH_USER_MODEL = getattr(
    settings, 'AUTH_USER_MODEL', 'django.contrib.auth.models.User')

CREDIT_ON_CREATE = _SETTINGS.get('CREDIT_ON_CREATE')
CONTRIBUTOR_RELATION = _SETTINGS.get('CONTRIBUTOR_RELATION')
MANAGER_RELATION = _SETTINGS.get('MANAGER_RELATION')
PROCESSOR_HOOK_URL = _SETTINGS.get('PROCESSOR_HOOK_URL')
PROVIDER_CALLABLE = _SETTINGS.get('PROVIDER_CALLABLE')
PROVIDER_ID = _SETTINGS.get('PROVIDER_ID')
PROCESSOR_ID = _SETTINGS.get('PROCESSOR_ID')

# BE EXTRA CAREFUL! This variable is used to bypass PermissionDenied
# exceptions. It is solely intended as a debug flexibility nob.
SKIP_PERMISSION_CHECK = _SETTINGS.get('SKIP_PERMISSION_CHECK')

STRIPE_PRIV_KEY = getattr(settings, 'STRIPE_PRIV_KEY', "Undefined")
STRIPE_PUB_KEY = getattr(settings, 'STRIPE_PUB_KEY', "Undefined")

