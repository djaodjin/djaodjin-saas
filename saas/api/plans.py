# Copyright (c) 2016, DjaoDjin inc.
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
from rest_framework import status
from rest_framework.response import Response

from .serializers import PlanSerializer
from ..mixins import ProviderMixin
from ..models import Plan, Subscription

#pylint: disable=no-init
#pylint: disable=old-style-class


class PlanActivateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Plan
        fields = ('is_active',)


class PlanMixin(ProviderMixin):

    model = Plan
    lookup_field = 'slug'
    lookup_url_kwarg = 'plan'

    def get_queryset(self):
        return Plan.objects.filter(organization=self.provider)

    def perform_create(self, serializer):
        unit = serializer.validated_data.get('unit', None)
        if unit is None:
            first_plan = self.get_queryset().first()
            if first_plan:
                unit = first_plan.unit
            else:
                unit = 'usd'
        serializer.save(organization=self.provider,
            slug=self.slugify(serializer.validated_data['title']),
            unit=unit)

    def perform_update(self, serializer):
        if ('title' in serializer.validated_data and
            not Subscription.objects.filter(plan=self.get_object()).exists()):
            # In case no subscription has ever been created for this ``Plan``
            # it seems safe to update its slug.
            # In cases some other resource's slug was derived on the initial
            # slug, we don't want to perform an update and get inconsistent
            # look of the derived URLs.
            # pylint: disable=protected-access
            serializer._validated_data['slug'] \
                = self.slugify(serializer.validated_data['title'])
        # We use PUT instead of PATCH otherwise we cannot run test units
        # on phantomjs. PUT would override the is_active if not present.
        serializer.save(organization=self.provider,
            is_active=serializer.validated_data.get('is_active',
                serializer.instance.is_active))

    @staticmethod
    def slugify(title):
        slug_base = slugify(title)
        i = 0
        slug = slug_base
        while Plan.objects.filter(slug__exact=slug).count() > 0:
            slug = slugify('%s-%d' % (slug_base, i))
            i += 1
        return slug


class PlanActivateAPIView(PlanMixin, UpdateAPIView):
    """
    Activate a plan, enabling users to subscribe to it, or deactivate
    a plan, disabling users from subscribing to it. Activation or
    deactivation is toggled based on the ``is_active`` field passed
    in the PUT request.

    **Example request**:

    .. sourcecode:: http

        PUT /api/profile/cowork/plans/activate

        {
            "is_active": true
        }
    """
    serializer_class = PlanActivateSerializer


class PlanCreateAPIView(PlanMixin, CreateAPIView):
    """
    Create a ``Plan`` for a provider.

    **Example request**:

    .. sourcecode:: http

        POST /api/profile/cowork/plans

        {
            "title": "Open Space",
            "description": "A desk in our coworking space",
            "is_active": false,
            "period_amount": 12000,
            "interval": 1
        }

    **Example response**:

    .. sourcecode:: http

        {
            "title": "Open Space",
            "description": "A desk in our coworking space",
            "is_active": false,
            "period_amount": 12000,
            "interval": 1
        }
    """

    serializer_class = PlanSerializer


class PlanResourceView(PlanMixin, RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a ``Plan``.

    **Example response**:

    .. sourcecode:: http

        {
            "title": "Open Space",
            "description": "A desk in our coworking space",
            "is_active": false,
            "period_amount": 12000,
            "interval": 1
        }
    """

    serializer_class = PlanSerializer

    def destroy(self, request, *args, **kwargs): #pylint:disable=unused-argument
#        Override to provide some validation.
#
#        Without this, users could subvert the "no deleting plans with
#        subscribers" rule via URL manipulation.
#
#        Override destroy() instead of perform_destroy() to
#        return a custom 403 response.
#        By using PermissionDenied django exception
#        django rest framework return a default 403 with
#        {'detail': 'permission denied'}
#        https://github.com/tomchristie/django-rest-framework\
#          /blob/master/rest_framework/views.py#L55
        instance = self.get_object()
        if instance.subscription_set.count() != 0:
            return Response(
                {'detail':'Cannot delete a plan with subscribers'},
                status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
