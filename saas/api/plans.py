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

from django.template.defaultfilters import slugify
from rest_framework.generics import (CreateAPIView,
    RetrieveUpdateDestroyAPIView, UpdateAPIView)
from rest_framework import serializers

from saas.models import Plan
from saas.mixins import OrganizationMixin

#pylint: disable=no-init
#pylint: disable=old-style-class


class PlanSerializer(serializers.ModelSerializer):

    class Meta:
        model = Plan
        fields = ('slug', 'title', 'description', 'is_active',
                  'setup_amount', 'period_amount', 'interval')
        read_only_fields = ('slug',)


class PlanActivateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Plan
        fields = ('is_active',)


class PlanMixin(OrganizationMixin):

    model = Plan
    slug_url_kwarg = 'plan'

    def get_queryset(self):
        queryset = super(PlanMixin, self).get_queryset()
        return queryset.filter(organization__slug=self.kwargs.get(
                self.organization_url_kwarg))

    @staticmethod
    def slugify(obj):
        slug = slugify(obj.title)
        i = 0
        while Plan.objects.filter(slug__exact=slug).count() > 0:
            slug = slugify('%s-%d' % (slug, i))
            i += 1
        setattr(obj, 'slug', slug)



class PlanActivateAPIView(PlanMixin, UpdateAPIView):

    serializer_class = PlanActivateSerializer


class PlanCreateAPIView(PlanMixin, CreateAPIView):

    serializer_class = PlanSerializer

    def pre_save(self, obj):
        obj.organization = self.get_organization()
        self.slugify(obj)


class PlanResourceView(PlanMixin, RetrieveUpdateDestroyAPIView):

    serializer_class = PlanSerializer

    def pre_save(self, obj):
        if 'slug' in self.request.DATA:
            # Only when a slug field is passed will we force recompute it here.
            # In cases some other resource's slug was derived on the initial
            # slug, we don't want to do this to prevent inconsistent look
            # of the derived URLs.
            self.slugify(obj)

