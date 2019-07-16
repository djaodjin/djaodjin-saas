# Copyright (c) 2019, DjaoDjin inc.
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

#pylint:disable=useless-super-delegation

from rest_framework import status
from rest_framework.generics import (ListCreateAPIView,
    RetrieveUpdateDestroyAPIView)
from rest_framework.response import Response

from .serializers import PlanSerializer
from ..mixins import PlanMixin
from ..filters import DateRangeFilter, OrderingFilter
from ..models import Plan, Subscription
from .. import settings


class PlanListCreateAPIView(PlanMixin, ListCreateAPIView):
    """
    Lists a provider plans

    Returns a PAGE_SIZE list of plans whose provider is {organization}.

    **Tags: subscriptions

    **Examples

    .. code-block:: http

         GET /api/profile/cowork/plans HTTP/1.1

    responds

    .. code-block:: json

        {
          "count": 1,
          "next": null,
          "previous": null,
          "results": [{
            "slug": "managed",
            "title": "Managed",
            "description": "Ideal for growing organizations",
            "is_active": true,
            "setup_amount": 0,
            "period_amount": 2900,
            "period_length": 1,
            "interval": "monthly",
            "advance_discount": 0,
            "unit": "usd",
            "is_not_priced": false,
            "renewal_type": "auto-renew",
            "created_at": "2019-01-01T00:00:00Z",
            "organization": "cowork",
            "extra": null,
            "skip_optin_on_grant": false,
            "optin_on_request": false
          }]
        }
    """
    serializer_class = PlanSerializer
    filter_backends = (DateRangeFilter, OrderingFilter)
    ordering_fields = [
        ('title', 'title'),
        ('period_amount', 'period_amount'),
        ('is_active', 'is_active'),
        ('created_at', 'created_at')]

    def post(self, request, *args, **kwargs):
        """
        Creates a subscription plan

        Creates a subscription plan for provider {organization}.

        **Tags: subscriptions

        **Examples

        .. code-block:: http

             POST /api/profile/cowork/plans HTTP/1.1

        .. code-block:: json

            {
                "title": "Open Space",
                "description": "A desk in our coworking space",
                "is_active": false,
                "period_amount": 12000,
                "interval": 1
            }

        responds

        .. code-block:: json

            {
                "title": "Open Space",
                "description": "A desk in our coworking space",
                "is_active": false,
                "period_amount": 12000,
                "interval": 1
            }
        """
        return super(PlanListCreateAPIView, self).post(request, *args, **kwargs)

    def get_queryset(self):
        self.queryset = self.organization.plans.all()
        return super(PlanListCreateAPIView, self).get_queryset()

    def perform_create(self, serializer):
        unit = serializer.validated_data.get('unit', None)
        if not unit:
            first_plan = self.get_queryset().first()
            if first_plan:
                unit = first_plan.unit
            else:
                unit = settings.DEFAULT_UNIT
        serializer.save(organization=self.provider, unit=unit)


class PlanDetailAPIView(PlanMixin, RetrieveUpdateDestroyAPIView):
    """
    Retrieves a subscription plan

    Returns the {plan} for provider {organization}

    The ``is_active`` boolean is used to activate a plan, enabling users
    to subscribe to it, or deactivate a plan, disabling users from subscribing
    to it.

    **Tags: subscriptions

    **Examples

    .. code-block:: http

        GET /api/profile/cowork/plans/open-space HTTP/1.1

    responds

    .. code-block:: json

        {
            "title": "Open Space",
            "description": "A desk in our coworking space",
            "is_active": false,
            "period_amount": 12000,
            "interval": 1
        }
    """
    serializer_class = PlanSerializer

    def delete(self, request, *args, **kwargs):
        """
        Deletes a subscription plan

        A plan can only be deleted when there are no subscriptions to it.
        Even if all subscriptions to a plan have expired, the plan cannot
        be deleted. It should be de-activated instead such that no customers
        can subscribes to it.

        **Tags: subscriptions

        **Examples

        .. code-block:: http

            DELETE /api/profile/cowork/plans/open-space HTTP/1.1
        """
        return super(PlanDetailAPIView, self).delete(request, *args, **kwargs)

    def get_queryset(self):
        return Plan.objects.filter(organization=self.provider)

    def get_object(self):
        return self.plan

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

    def get_serializer_context(self):
        context = super(PlanDetailAPIView, self).get_serializer_context()
        context.update({'provider': self.provider})
        return context

    def perform_update(self, serializer):
        title = serializer.validated_data.get('title', None)
        if (title and
            title != serializer.instance.title and
            not Subscription.objects.filter(plan=serializer.instance).exists()):
            # OK to use ``filter`` here since grants/requests should also be
            # included.
            # In case no subscription has ever been created for this ``Plan``
            # it seems safe to update its slug.
            # In cases some other resource's slug was derived on the initial
            # slug, we don't want to perform an update and get inconsistent
            # look of the derived URLs.
            # pylint: disable=protected-access
            serializer.instance.slug = None
        # We use PUT instead of PATCH otherwise we cannot run test units
        # on phantomjs. PUT would override the is_active if not present.
        serializer.save(organization=self.provider,
            is_active=serializer.validated_data.get('is_active',
                serializer.instance.is_active))

    def put(self, request, *args, **kwargs):
        """
        Updates a subscription plan

        Updates fields for {plan}. If the ``period_amount`` is modified,
        all subscriptions to this plan will be charged the ``period_amount``
        on renewal.

        The ``is_active`` boolean is used to activate a plan, enabling users
        to subscribe to it, or deactivate a plan, disabling users
        from subscribing to it.

        **Tags: subscriptions

        **Examples

        .. code-block:: http

            PUT /api/profile/cowork/plans/open-space HTTP/1.1

        .. code-block:: json

            {
                "title": "Open Space"
            }

        responds

        .. code-block:: json

            {
                "title": "Open Space",
                "description": "A desk in our coworking space",
                "is_active": false,
                "period_amount": 12000,
                "interval": 1
            }
        """
        return super(PlanDetailAPIView, self).put(request, *args, **kwargs)
