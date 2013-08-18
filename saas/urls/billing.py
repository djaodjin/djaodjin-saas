# Copyright (c) 2013, Fortylines LLC
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

'''Billing urls'''

from django.conf.urls import patterns, include, url

from saas.backends import processor_hook
from saas.views.billing import (
    TransactionListView, update_card, pay_now)
from saas.settings import ACCT_REGEX, PROCESSOR_HOOK_URL

urlpatterns = patterns(
    'saas.views.billing',
    url(r'^processor_hook/%s' % PROCESSOR_HOOK_URL,
        processor_hook, name='saas_processor_hook_XXX'),
    url(r'^(?P<organization_id>%s)/card' % ACCT_REGEX,
        update_card, name='saas_update_card'),
    url(r'^(?P<organization_id>%s)/pay' % ACCT_REGEX,
        pay_now, name='saas_pay_now'),
    url(r'^(?P<organization_id>%s)' % ACCT_REGEX,
        TransactionListView.as_view(), name='saas_billing_info'),
)


