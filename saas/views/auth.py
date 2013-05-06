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

'''Authentication should be called ot each view entry point.'''

import logging

from django.http import Http404
from django.core.exceptions import PermissionDenied

from saas.models import Organization

# BE EXTRA CAREFUL! This variable is used to bypass PermissionDenied
# exceptions. It is solely intended as a debug flexibility nob.
SKIP_PERMISSION_CHECK = False
LOGGER = logging.getLogger(__name__)

def valid_manager_for_organization(user, organization):
    '''This will return a Organization object or raise different exceptions
    that can be forwarded as html feedback to the user.'''
    if isinstance(organization, basestring):
        try:
            organization = Organization.objects.get(name=organization)
        except Organization.DoesNotExist:
            raise Http404
    if not (user and organization.managers.filter(pk=user.id).exists()):
        if SKIP_PERMISSION_CHECK:
            LOGGER.warning("Skip permission denied for %s on organization %s",
                           user.username, organization.name)
        else:
            raise PermissionDenied
    return organization
