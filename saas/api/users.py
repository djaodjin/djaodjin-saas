# Copyright (c) 2015, DjaoDjin inc.
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

from django.core import validators
from django.http import Http404
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers, status
from rest_framework.generics import (DestroyAPIView, ListCreateAPIView)
from rest_framework.response import Response

from saas import get_contributor_relation_model, get_manager_relation_model
from saas.compat import User
from saas.mixins import OrganizationMixin, RelationMixin

#pylint: disable=no-init
#pylint: disable=old-style-class

class UserSerializer(serializers.ModelSerializer):

    # Only way I found out to remove the ``UniqueValidator``. We are not
    # interested to create new instances here.
    username = serializers.CharField(validators=[
        validators.RegexValidator(r'^[\w.@+-]+$', _('Enter a valid username.'),
            'invalid')])

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')


class RelationListAPIView(OrganizationMixin, ListCreateAPIView):

    queryset = User.objects.all()
    serializer_class = UserSerializer

    def add_relation(self, user, reason=None):
        raise NotImplementedError(
            "add_relation should be overriden in derived classes.")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = User.objects.get(
                username=serializer.validated_data['username'])
        except User.DoesNotExist:
            try:
                # The following SQL query is not folded into the previous
                # one so we can have a priority of username over email.
                user = User.objects.get(
                    email=serializer.validated_data['username'])
            except User.DoesNotExist:
                if not request.GET.get('force', False):
                    raise Http404("%s not found"
                        % serializer.validated_data['username'])
                full_name = serializer.validated_data.get('full_name', '')
                name_parts = full_name.split(' ')
                if len(name_parts) > 0:
                    first_name = name_parts[0]
                    last_name = ' '.join(name_parts[1:])
                else:
                    first_name = full_name
                    last_name = ''
                #pylint: disable=no-member
                user = User.objects.create_inactive_user(
                    serializer.validated_data['email'],
                    username=serializer.validated_data['username'],
                    first_name=first_name, last_name=last_name)

        self.organization = self.get_organization()
        if self.add_relation(user,
                reason=force_text(request.DATA.get('invite', None))):
            resp_status = status.HTTP_201_CREATED
        else:
            resp_status = status.HTTP_200_OK
        # We were going to return the list of managers here but
        # angularjs complains about deserialization of a list
        # while expecting a single object.
        return Response(serializer.validated_data, status=resp_status,
            headers=self.get_success_headers(serializer.validated_data))


class ContributorListAPIView(RelationListAPIView):

    def add_relation(self, user, reason=None):
        return self.organization.add_contributor(user, reason=reason)

    def get_queryset(self):
        queryset = super(ContributorListAPIView, self).get_queryset()
        return queryset.filter(contributes__slug=self.kwargs.get(
                self.organization_url_kwarg))


class ContributorDetailAPIView(RelationMixin, DestroyAPIView):

    model = get_contributor_relation_model()


class ManagerListAPIView(RelationListAPIView):

    def add_relation(self, user, reason=None):
        return self.organization.add_manager(user, reason=reason)

    def get_queryset(self):
        queryset = super(ManagerListAPIView, self).get_queryset()
        return queryset.filter(manages__slug=self.kwargs.get(
                self.organization_url_kwarg))


class ManagerDetailAPIView(RelationMixin, DestroyAPIView):

    model = get_manager_relation_model()


