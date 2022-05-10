# Copyright (c) 2021, DjaoDjin inc.
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
from __future__ import unicode_literals

from importlib import import_module

from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from stripe.error import APIConnectionError as ProcessorConnectionError

from .. import settings
from ..compat import (import_string, gettext_lazy as _,
    python_2_unicode_compatible)


@python_2_unicode_compatible
class ProcessorError(RuntimeError):

    def __init__(self, message, backend_except=None):
        super(ProcessorError, self).__init__(message)
        self.backend_except = backend_except

    def __str__(self):
        result = super(ProcessorError, self).__str__()
        if django_settings.DEBUG and self.backend_except:
            result += self.processor_details()
        return result

    def processor_details(self):
        return "(processor exception: %s)" % str(self.backend_except)


@python_2_unicode_compatible
class ProcessorSetupError(ProcessorError):
    """
    Error class specific for setup of processor account
    (i.e. none or invalid keys)
    """

    def __init__(self, message, provider, backend_except=None):
        super(ProcessorSetupError, self).__init__(
            message, backend_except=backend_except)
        self.provider = provider

    def __str__(self):
        result = super(ProcessorSetupError, self).__str__()
        result += '(provider: %s)' % str(self.provider)
        return result


@python_2_unicode_compatible
class CardError(ProcessorError):

    def __init__(self, message, code,
                 charge_processor_key=None, backend_except=None):
        super(CardError, self).__init__(message, backend_except=backend_except)
        self.code = code
        self.charge_processor_key = charge_processor_key

    def __str__(self):
        if self.code == 'card_declined':
            return str(_("Your card was declined. We are taking your security"\
" seriously. When we submit a charge to your bank, they have automated"\
" systems that determine whether or not to accept the charge. Check you"\
" entered the card  number, expiration date, CVC and address correctly."\
" If problems persist, please contact your bank."))
        return super(CardError, self).__str__()


def load_backend(path):
    dot_pos = path.rfind('.')
    module, attr = path[:dot_pos], path[dot_pos + 1:]
    try:
        mod = import_module(module)
    except (ImportError, ValueError) as err:
        raise ImproperlyConfigured(
            'Error importing backend %s: "%s"' % (path, err))
    try:
        cls = getattr(mod, attr)
    except AttributeError:
        raise ImproperlyConfigured('Module "%s" does not define a "%s"'\
' backend' % (module, attr))
    return cls()


def get_processor_backend(provider):
    if settings.PROCESSOR_BACKEND_CALLABLE:
        func = import_string(settings.PROCESSOR_BACKEND_CALLABLE)
        processor_backend = func(provider)
    else:
        processor_backend = load_backend(settings.PROCESSOR['BACKEND'])
    return processor_backend
