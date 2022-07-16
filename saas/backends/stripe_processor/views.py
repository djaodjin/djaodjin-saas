# Copyright (c) 2022, DjaoDjin inc.
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

import logging

from django.shortcuts import get_object_or_404
from django.views.generic import RedirectView
from rest_framework.response import Response
from rest_framework.views import APIView
import stripe

from ... import settings
from ...compat import import_string
from ...models import Charge, get_broker


LOGGER = logging.getLogger(__name__)


class StripeProcessorRedirectView(RedirectView):
    """
    Stripe will call an hard-coded URL hook. We normalize the ``state``
    parameter into a actual slug part of the URL and redirect there.
    """
    slug_url_kwarg = settings.PROFILE_URL_KWARG
    query_string = True

    def get_redirect_url(self, *args, **kwargs):
        redirect_func_name = settings.PROCESSOR.get('REDIRECT_CALLABLE', None)
        if redirect_func_name:
            func = import_string(redirect_func_name)
            url = func(self.request, site=kwargs.get(self.slug_url_kwarg))
            args = self.request.META.get('QUERY_STRING', '')
            if args and self.query_string:
                url = "%s?%s" % (url, args)
        else:
            url = super(StripeProcessorRedirectView, self).get_redirect_url(
                *args, **kwargs)
        return url

    def get(self, request, *args, **kwargs):
        self.permanent = False # XXX seems necessary...
        provider = request.GET.get('state', None)
        kwargs.update({self.slug_url_kwarg: provider})
        return super(StripeProcessorRedirectView, self).get(
            request, *args, **kwargs)


class StripeWebhook(APIView):
    """
    Answers callback from Stripe.

    **Examples**

    .. code-block:: http

        POST /api/stripe/postevent HTTP/1.1

    .. code-block:: json

        {}
    """
    schema = None

    def post(self, request, *args, **kwargs):
        #pylint:disable=unused-argument,no-self-use
        processor_backend = get_broker().processor_backend
        stripe.api_key = processor_backend.priv_key

        endpoint_secret = settings.PROCESSOR_HOOK_SECRET
        payload = request.body
        sig_header = request.META['HTTP_STRIPE_SIGNATURE']
        event = None

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except (ValueError, stripe.error.SignatureVerificationError) as err:
            # Invalid payload or invalid signature
            LOGGER.warning("Received %s on Stripe webhook", err)
            return Response(status=400)

        LOGGER.info("Posted stripe '%s' event %s PASS", event.type, event.id,
            extra={'processor': 'stripe', 'event': event.type,
                'event_id': event.id,
                'request': request})

        event_type = event.type
        if event_type in ['charge.succeeded', 'charge.failed',
                          'charge.refunded', 'charge.captured']:
            charge = get_object_or_404(Charge,
                processor_key=event.data.object.id)
            #pylint:disable=protected-access
            processor_backend._update_charge_state(charge,
                stripe_charge=event.data.object, event_type=event_type)
        elif event_type in ['charge.dispute.created',
                'charge.dispute.updated', 'charge.dispute.closed']:
            if event_type == 'charge.dispute.closed':
                if event.data.object.status == 'won':
                    event_type = 'charge.dispute.closed.won'
                elif event.data.object.status == 'lost':
                    event_type = 'charge.dispute.closed.lost'
            charge = get_object_or_404(Charge,
                processor_key=event.data.object.charge)
            #pylint:disable=protected-access
            processor_backend._update_charge_state(
                charge, event_type=event_type)

        return Response("OK")
