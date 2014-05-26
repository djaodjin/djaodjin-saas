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

'''Authentication should be called ot each view entry point.'''

import logging

from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from saas.models import Organization
from saas.settings import SKIP_PERMISSION_CHECK

LOGGER = logging.getLogger(__name__)

def managed_organizations(user):
    """
    List of organization this user is a manager for.
    """
    queryset = []
    for org in Organization.objects.all().order_by('slug'):
        try:
            queryset += [
                valid_manager_for_organization(user, org)]
        except PermissionDenied:
            pass
    return queryset


def valid_manager_for_organization(user, organization):
    """
    Returns *organization* as an Organization instance if *user*
    is a manager of *organization* and raises a ``PermissionDenied``
    exception otherwise.

    To simplify logic that checks permissions, the function will accept
    *organization* to either be an Organization instance or a ``string``
    that represents the name of an organization.
    """
    if not isinstance(organization, Organization):
        organization = get_object_or_404(Organization, slug=organization)

    if SKIP_PERMISSION_CHECK:
        if user:
            username = user.username
        else:
            username = '(none)'
        LOGGER.warning("Skip permission check for %s on organization %s",
                       username, organization)
        return organization

    if user and user.is_authenticated():
        # Walk-up the organization tree until we hit a valid manager
        # relationship or we found the root of the organization tree.
        org_node = organization
        while org_node and not org_node.managers.filter(pk=user.id).exists():
            org_node = org_node.belongs
        if org_node and org_node.managers.filter(pk=user.id).exists():
            return organization
    raise PermissionDenied


def valid_contributor(user, organization):
    """
    Returns a tuple (*organization*, *is_manager*) where *organization*
    is an Organization instance and *is_manager* is ``True`` when the
    user is also a manager for the *organization*.

    This function will raise a ``PermissionDenied`` exception when the
    *user* is neither a contributor nor a manager to the *organization*.

    To simplify logic that checks permissions, the function will accept
    *organization* to either be an Organization instance or a ``string``
    that represents the name of an organization.
    """
    if not isinstance(organization, Organization):
        organization = Organization.objects.get(slug=organization)

    if SKIP_PERMISSION_CHECK:
        if user:
            username = user.username
        else:
            username = '(none)'
        LOGGER.warning("Skip permission check for %s on organization %s",
                       username, organization)
        return organization, True

    try:
        _ = valid_manager_for_organization(user, organization)
        return organization, True
    except PermissionDenied:
        pass

    if user and user.is_authenticated():
        # Walk-up the organization tree until we hit a valid contributor
        # relationship or we found the root of the organization tree.
        org_node = organization
        while (org_node
               and not org_node.contributors.filter(pk=user.id).exists()):
            org_node = org_node.belongs
        if org_node and org_node.contributors.filter(pk=user.id).exists():
            return organization, False
    raise PermissionDenied
