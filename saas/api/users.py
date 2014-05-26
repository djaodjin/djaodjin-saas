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

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework import status
from rest_framework.generics import (DestroyAPIView, ListAPIView,
    ListCreateAPIView)
from rest_framework.response import Response

from saas import get_contributor_relation_model, get_manager_relation_model
from saas.compat import User
from saas.mixins import OrganizationMixin, RelationMixin

#pylint: disable=no-init
#pylint: disable=old-style-class

class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')

    def full_clean(self, instance):
        # Implementation Note:
        # We only want to make sure we get a correctly formatted username
        # without validating the User is unique in the database. rest_framework
        # does not propagate the flag here so we override the method.
        try:
            instance.full_clean(exclude=self.get_validation_exclusions(),
                                validate_unique=False)
        except ValidationError as err:
            self._errors = err.message_dict
            return None
        return instance


class RelationListAPIView(OrganizationMixin, ListCreateAPIView):

    model = User
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        #pylint: disable=no-member
        serializer = self.get_serializer(data=request.DATA, files=request.FILES)
        if serializer.is_valid():
            user = get_object_or_404(User, username=serializer.data['username'])
            self.organization = self.get_organization()
            if self.add_relation(user):
                resp_status = status.HTTP_201_CREATED
            else:
                resp_status = status.HTTP_200_OK
            # We were going to return the list of managers here but
            # angularjs complains about deserialization of a list
            # while expecting a single object.
            return Response(serializer.data, status=resp_status,
                headers=self.get_success_headers(serializer.data))

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ContributorListAPIView(RelationListAPIView):

    def add_relation(self, user):
        return self.organization.add_contributor(user)

    def get_queryset(self):
        queryset = super(ContributorListAPIView, self).get_queryset()
        return queryset.filter(contributes__slug=self.kwargs.get(
                self.organization_url_kwarg))


class ContributorDetailAPIView(RelationMixin, DestroyAPIView):

    model = get_contributor_relation_model()


class ManagerListAPIView(RelationListAPIView):

    def add_relation(self, user):
        return self.organization.add_manager(user)

    def get_queryset(self):
        queryset = super(ManagerListAPIView, self).get_queryset()
        return queryset.filter(manages__slug=self.kwargs.get(
                self.organization_url_kwarg))


class ManagerDetailAPIView(RelationMixin, DestroyAPIView):

    model = get_manager_relation_model()


class UserListAPIView(ListAPIView):

    model = User
    serializer_class = UserSerializer

    def get_queryset(self):
        queryset = super(UserListAPIView, self).get_queryset()
        startswith = self.request.GET.get('q', None)
        if not startswith:
            raise Http404
        return queryset.filter(Q(username__startswith=startswith)
            | Q(email__startswith=startswith))

