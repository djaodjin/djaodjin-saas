# Copyright (c) 2016, DjaoDjin inc.
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

from django.views.generic import RedirectView

from ... import settings


class StripeProcessorRedirectView(RedirectView):
    """
    Stripe will call an hard-coded URL hook. We normalize the ``state``
    parameter into a actual slug part of the URL and redirect there.
    """
    slug_url_kwarg = 'organization'
    query_string = True

    def get_redirect_url(self, *args, **kwargs):
        redirect_func_name = settings.PROCESSOR.get('REDIRECT_CALLABLE', None)
        if redirect_func_name:
            from saas.compat import import_string
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
