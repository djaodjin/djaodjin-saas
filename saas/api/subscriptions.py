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

from rest_framework.generics import (
    ListCreateAPIView, RetrieveUpdateDestroyAPIView)
from rest_framework.response import Response
from rest_framework import serializers

from saas.utils import datetime_or_now
from saas.mixins import SubscriptionMixin
from saas.models import Subscription

#pylint: disable=no-init,old-style-class


class SubscriptionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Subscription


class SubscriptionListAPIView(SubscriptionMixin, ListCreateAPIView):

    serializer_class = SubscriptionSerializer


class SubscriptionDetailAPIView(SubscriptionMixin,
                                RetrieveUpdateDestroyAPIView):

    serializer_class = SubscriptionSerializer

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.ends_at = datetime_or_now()
        self.object.save()
        serializer = self.get_serializer(self.object)
        return Response(serializer.data) #pylint: disable=no-member
