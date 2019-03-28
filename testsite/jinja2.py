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

from __future__ import absolute_import

from django.conf import settings
import django.template.defaultfilters
from django.utils.translation import gettext, ngettext
from jinja2.sandbox import SandboxedEnvironment as Jinja2Environment
import saas.templatetags.saas_tags

import testsite.templatetags.testsite_tags


def environment(**options):
    options['extensions'] = ['jinja2.ext.i18n']

    env = Jinja2Environment(**options)

    # i18n
    env.install_gettext_callables(gettext=gettext, ngettext=ngettext,
        newstyle=True)

    # Generic filters to render pages
    env.filters['is_authenticated'] = \
        testsite.templatetags.testsite_tags.is_authenticated
    env.filters['iteritems'] = saas.templatetags.saas_tags.iteritems
    env.filters['isoformat'] = saas.templatetags.saas_tags.isoformat
    env.filters['messages'] = testsite.templatetags.testsite_tags.messages
    env.filters['pluralize'] = django.template.defaultfilters.pluralize
    env.filters['to_json'] = testsite.templatetags.testsite_tags.to_json
    env.filters['url_profile'] = testsite.templatetags.testsite_tags.url_profile

    # Specific to SaaS
    env.filters['humanize_money'] = saas.templatetags.saas_tags.humanize_money
    env.filters['humanize_period'] = saas.templatetags.saas_tags.humanize_period
    env.filters['date_in_future'] = saas.templatetags.saas_tags.date_in_future
    env.filters['md'] = saas.templatetags.saas_tags.md
    env.filters['describe'] = saas.templatetags.saas_tags.describe

    env.globals.update({
        'VUEJS': (settings.JS_FRAMEWORK == 'vuejs'),
        'DATETIME_FORMAT': "MMM dd, yyyy",
    })

    return env
