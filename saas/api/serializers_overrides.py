# Copyright (c) 2022, DjaoDjin inc.
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
"""
Default implementation when not overriden
"""

from __future__ import unicode_literals

from django.core import validators
from django.contrib.auth import get_user_model
from rest_framework import serializers

from ..compat import gettext_lazy as _


class UserSerializer(serializers.ModelSerializer):

    # Only way I found out to remove the ``UniqueValidator``. We are not
    # interested to create new instances here.
    slug = serializers.CharField(source='username', validators=[
        validators.RegexValidator(r'^[\w.@+-]+$', _('Enter a valid username.'),
            'invalid')],
        help_text=_("Effectively the username. The variable is named `slug`"\
            " such that front-end code can be re-used between Organization"\
            " and User records."))
    email = serializers.EmailField(read_only=True,
        help_text=_("E-mail address for the user"))
    created_at = serializers.DateTimeField(source='date_joined', required=False,
        help_text=_("Date/time of creation (in ISO format)"))
    last_login = serializers.DateTimeField(required=False,
        help_text=_("Date/time of last login (in ISO format)"))
    full_name = serializers.SerializerMethodField(
        help_text=_("Full name for the contact (effectively first name"\
        " followed by last name)"))

    class Meta:
        model = get_user_model()
        fields = ('slug', 'email', 'full_name', 'created_at', 'last_login')
        read_only = ('full_name', 'created_at', 'last_login')

    @staticmethod
    def get_full_name(obj):
        return obj.get_full_name()
