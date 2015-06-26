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

from rest_framework.generics import (ListAPIView,
    ListCreateAPIView, RetrieveUpdateDestroyAPIView)
from rest_framework.response import Response
from rest_framework import serializers
from extra_views.contrib.mixins import SearchableListMixin, SortableListMixin

from saas.utils import datetime_or_now
from saas.models import Organization, Subscription
from saas.mixins import OrganizationMixin, SubscriptionMixin
from saas.api.serializers import PlanSerializer

#pylint: disable=no-init,old-style-class


class OrganizationSerializer(serializers.ModelSerializer):

    printable_name = serializers.CharField(read_only=True)

    class Meta:
        model = Organization
        fields = ('slug', 'printable_name', )


class SubscriptionSerializer(serializers.ModelSerializer):

    organization = OrganizationSerializer(read_only=True)
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = ('created_at', 'ends_at', 'description',
                  'organization', 'plan',)


class SubscriptionListAPIView(SubscriptionMixin, ListCreateAPIView):

    serializer_class = SubscriptionSerializer


class SubscriptionDetailAPIView(SubscriptionMixin,
                                RetrieveUpdateDestroyAPIView):

    serializer_class = SubscriptionSerializer

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.unsubscribe_now()
        serializer = self.get_serializer(self.object)
        return Response(serializer.data) #pylint: disable=no-member


class ActiveSubscriptionBaseAPIView(OrganizationMixin, ListAPIView):

    model = Subscription

    def get_queryset(self):
        self.organization = self.get_organization()
        return Subscription.objects.filter(
            ends_at__gte=datetime_or_now(),
            plan__organization=self.organization).distinct()


class SmartListMixin(SearchableListMixin, SortableListMixin):
    """
    Subscriber list which is also searchable and sortable.
    """
    search_fields = ['organization__slug',
                     'organization__full_name',
                     'organization__email',
                     'organization__phone',
                     'organization__street_address',
                     'organization__locality',
                     'organization__region',
                     'organization__postal_code',
                     'organization__country',
                     'plan__title']

    sort_fields_aliases = [('organization__full_name', 'organization'),
                           ('plan__title', 'plan'),
                           ('created_at', 'created_at'),
                           ('ends_at', 'ends_at')]


class ActiveSubscriptionAPIView(SmartListMixin, ActiveSubscriptionBaseAPIView):

    serializer_class = SubscriptionSerializer
    paginate_by = 25

