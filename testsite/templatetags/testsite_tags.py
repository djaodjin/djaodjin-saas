# Copyright (c) 2018, DjaoDjin inc.
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

import json

from django import template
from django.contrib.messages.api import get_messages
from django.forms import BaseForm
from django.utils import six
from django.utils.safestring import mark_safe
from saas.compat import is_authenticated as is_authenticated_base, reverse
from saas.templatetags.saas_tags import attached_organization


register = template.Library()


@register.filter()
def is_authenticated(request):
    return is_authenticated_base(request)


@register.filter()
def messages(obj):
    """
    Messages to be displayed to the current session.
    """
    if isinstance(obj, BaseForm):
        return obj.non_field_errors()
    return get_messages(obj)


@register.filter
def to_json(value):
    if isinstance(value, six.string_types):
        return value
    return mark_safe(json.dumps(value))


@register.filter()
def url_profile(request):
    if is_authenticated_base(request):
        organization = attached_organization(request.user)
        if organization:
            return reverse('saas_organization_profile', args=(organization,))
        return reverse('users_profile', args=(request.user,))
    return None
