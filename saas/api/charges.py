# Copyright (c) 2014, Fortylines LLC
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

from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.generics import RetrieveAPIView
from rest_framework import serializers

from saas import signals
from saas.models import Charge
from saas.mixins import ChargeMixin

#pylint: disable=no-init
#pylint: disable=old-style-class

class ChargeSerializer(serializers.ModelSerializer):

    state = serializers.CharField(source='get_state_display')

    class Meta:
        model = Charge
        fields = ('created_at', 'amount', 'description', 'last4', 'exp_date',
                  'processor_id', 'state')


class ChargeResourceView(ChargeMixin, RetrieveAPIView):

    serializer_class = ChargeSerializer


class EmailChargeReceiptAPIView(ChargeMixin, GenericAPIView):
    """
    Email the charge receipt to the request user.
    """
    #pylint: disable=unused-variable
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        signals.charge_updated.send(
            sender=__name__, charge=self.object, user=request.user)
        return Response({
            "charge_id": self.object.processor_id, "email": request.user.email})
