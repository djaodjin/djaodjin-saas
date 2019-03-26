# Copyright (c) 2019, DjaoDjin inc.
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

"""Command to generate JavaScript file used for i18n on the frontend"""

import json, os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.views.i18n import JavaScriptCatalog, js_catalog_template
from django.template import Context, Engine
from django.utils.translation import get_language
from django.utils.translation.trans_real import DjangoTranslation

class Command(BaseCommand):
    """Generate JavaScript file for i18n purposes"""
    help = 'Generate JavaScript file for i18n purposes'

    def add_arguments(self, parser):
        parser.add_argument('PATH', nargs=1, type=str)

    def handle(self, *args, **options):
        contents = self.generate_i18n_js()
        path = os.path.join(settings.BASE_DIR, options['path'][0])
        with open(path, 'w') as f:
            f.write(contents)
        self.stdout.write('wrote file into %s\n' % path)

    def generate_i18n_js(self):
        class InlineJavaScriptCatalog(JavaScriptCatalog):
            def render_to_str(self):
                self.translation = DjangoTranslation(settings.LANGUAGE_CODE
                    , domain=self.domain)
                context = self.get_context_data()
                template = Engine().from_string(js_catalog_template)
                context['catalog_str'] = indent(
                    json.dumps(context['catalog'], sort_keys=True, indent=2)
                ) if context['catalog'] else None
                context['formats_str'] = json.dumps(context['formats'],
                    sort_keys=True, indent=2)
                return template.render(Context(context))

        return InlineJavaScriptCatalog().render_to_str()
