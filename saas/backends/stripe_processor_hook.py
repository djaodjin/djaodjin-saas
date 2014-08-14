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

import logging

import stripe
from django.conf import settings as django_settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response

from saas.backends.stripe_processor import StripeBackend
from saas.models import Charge

LOGGER = logging.getLogger('django.request') # We want ADMINS to about this.

@api_view(['POST'])
def processor_hook(request):
    stripe.api_key = StripeBackend.priv_key
    # Attempt to validate the event by posting it back to Stripe.
    if django_settings.DEBUG:
        event = stripe.Event.construct_from(request.DATA, stripe.api_key)
    else:
        event = stripe.Event.retrieve(request.DATA['id'])
    if not event:
        LOGGER.error("Posted stripe event %s FAIL", request.DATA['id'])
        raise Http404
    LOGGER.info("Posted stripe event %s PASS", event.id)
    charge = get_object_or_404(Charge, processor_id=event.data.object.id)

    if event.type == 'charge.succeeded':
        if charge.state != charge.DONE:
            charge.payment_successful()
        else:
            LOGGER.warning(
                "Already received a charge.succeeded event for %s", charge)
    elif event.type == 'charge.failed':
        charge.failed()
    elif event.type == 'charge.refunded':
        charge.refund()
    elif event.type == 'charge.captured':
        charge.capture()
    elif event.type == 'charge.dispute.created':
        charge.dispute_created()
    elif event.type == 'charge.dispute.updated':
        charge.dispute_updated()
    elif event.type == 'charge.dispute.closed':
        charge.dispute_closed()

    return Response("OK")
