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

import re

from django.conf import settings
from django.contrib.auth import logout as auth_logout
from django.db import transaction
from rest_framework import status
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from rest_framework.response import Response

from saas.api.serializers import OrganizationSerializer
from saas.mixins import OrganizationMixin
from saas.models import Organization

#pylint: disable=no-init
#pylint: disable=old-style-class

class OrganizationDetailAPIView(OrganizationMixin,
                                RetrieveUpdateDestroyAPIView):

    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

    def destroy(self, request, *args, **kwargs):
        """
        Archive the organization. We don't to loose the subscriptions
        and transactions history.
        """
        obj = self.get_organization()
        manager = self.attached_manager(obj)
        self.pre_delete(obj)
        email = obj.email
        slug = '_archive_%d' % obj.id
        look = re.match(r'.*(@\S+)', settings.ADMINS[0][1])
        if look:
            email = '%s+%d%s' % (obj.slug, obj.id, look.group(1))
        with transaction.atomic():
            if manager:
                manager.is_active = False
                manager.username = slug
                manager.email = email
                manager.save()
            obj.slug = slug
            obj.email = email
            obj.is_active = False
            obj.save()
        self.post_delete(obj)
        auth_logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)

