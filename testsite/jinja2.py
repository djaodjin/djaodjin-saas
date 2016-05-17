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

from __future__ import absolute_import

from jinja2.sandbox import SandboxedEnvironment as Jinja2Environment
import saas.templatetags.saas_tags

import testsite.templatetags.testsite_tags


def environment(**options):
    env = Jinja2Environment(**options)
    # Generic filters to render pages
    env.filters['messages'] = testsite.templatetags.testsite_tags.messages
    env.filters['as_html'] = testsite.templatetags.testsite_tags.as_html
    env.filters['url_profile_base'] = \
        testsite.templatetags.testsite_tags.url_profile_base
    env.filters['url_profile'] = testsite.templatetags.testsite_tags.url_profile
    env.filters['is_authenticated'] = \
        testsite.templatetags.testsite_tags.is_authenticated

    # Specific to SaaS
    env.filters['humanize_money'] = saas.templatetags.saas_tags.humanize_money
    env.filters['humanize_period'] = saas.templatetags.saas_tags.humanize_period
    env.filters['date_in_future'] = saas.templatetags.saas_tags.date_in_future
    env.filters['md'] = saas.templatetags.saas_tags.md
    env.filters['describe'] = saas.templatetags.saas_tags.describe

    return env
