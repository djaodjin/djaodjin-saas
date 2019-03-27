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
from django.views.i18n import JavaScriptCatalog, get_formats
from django.template import Context, Engine
from django.utils.translation import get_language
from django.utils.translation.trans_real import DjangoTranslation

js_catalog_template = r"""
{% autoescape off %}
(function(globals) {
  var activeLang = navigator.language || navigator.userLanguage || 'en';
  var django = globals.django || (globals.django = {});
  var plural = {{ plural }};
  django.pluralidx = function(n) {
    var v = plural[activeLang];
    if(v){
        if (typeof(v) == 'boolean') {
          return v ? 1 : 0;
        } else {
          return v;
        }
    } else {
        return (n == 1) ? 0 : 1;
    }
  };
  /* gettext library */
  django.catalog = django.catalog || {};
  {% if catalog_str %}
  var newcatalog = {{ catalog_str }};
  for (var ln in newcatalog) {
    django.catalog[ln] = newcatalog[ln];
  }
  {% endif %}
  if (!django.jsi18n_initialized) {
    django.gettext = function(msgid) {
      var lnCatalog = django.catalog[activeLang]
      if(lnCatalog){
          var value = lnCatalog[msgid];
          if (typeof(value) != 'undefined') {
            return (typeof(value) == 'string') ? value : value[0];
          }
      }
      return msgid;
    };
    django.ngettext = function(singular, plural, count) {
      var lnCatalog = django.catalog[activeLang]
      if(lnCatalog){
          var value = lnCatalog[singular];
          if (typeof(value) != 'undefined') {
          } else {
            return value.constructor === Array ? value[django.pluralidx(count)] : value;
          }
      }
      return (count == 1) ? singular : plural;
    };
    django.gettext_noop = function(msgid) { return msgid; };
    django.pgettext = function(context, msgid) {
      var value = django.gettext(context + '\x04' + msgid);
      if (value.indexOf('\x04') != -1) {
        value = msgid;
      }
      return value;
    };
    django.npgettext = function(context, singular, plural, count) {
      var value = django.ngettext(context + '\x04' + singular, context + '\x04' + plural, count);
      if (value.indexOf('\x04') != -1) {
        value = django.ngettext(singular, plural, count);
      }
      return value;
    };
    django.interpolate = function(fmt, obj, named) {
      if (named) {
        return fmt.replace(/%\(\w+\)s/g, function(match){return String(obj[match.slice(2,-2)])});
      } else {
        return fmt.replace(/%s/g, function(match){return String(obj.shift())});
      }
    };
    /* formatting library */
    django.formats = {{ formats_str }};
    django.get_format = function(format_type) {
      var value = django.formats[format_type];
      if (typeof(value) == 'undefined') {
        return format_type;
      } else {
        return value;
      }
    };
    /* add to global namespace */
    globals.pluralidx = django.pluralidx;
    globals.gettext = django.gettext;
    globals.ngettext = django.ngettext;
    globals.gettext_noop = django.gettext_noop;
    globals.pgettext = django.pgettext;
    globals.npgettext = django.npgettext;
    globals.interpolate = django.interpolate;
    globals.get_format = django.get_format;
    django.jsi18n_initialized = true;
  }
}(this));
{% endautoescape %}
"""


class Command(BaseCommand):
    """Generate JavaScript file for i18n purposes"""
    help = 'Generate JavaScript file for i18n purposes'

    def add_arguments(self, parser):
        parser.add_argument('PATH', nargs=1, type=str)

    def handle(self, *args, **options):
        contents = self.generate_i18n_js()
        path = os.path.join(settings.BASE_DIR, options['PATH'][0])
        with open(path, 'w') as f:
            f.write(contents)
        self.stdout.write('wrote file into %s\n' % path)

    def generate_i18n_js(self):
        class InlineJavaScriptCatalog(JavaScriptCatalog):
            def render_to_str(self):
                # hardcoding locales as it is not trivial to
                # get user apps and its locales, and including
                # all django supported locales is not efficient
                codes = ['en', 'de', 'ru', 'es', 'fr', 'pt']
                catalog = {}
                plural = {}
                # this function is not i18n-enabled
                formats = get_formats()
                for code in codes:
                    self.translation = DjangoTranslation(code, domain=self.domain)
                    _catalog = self.get_catalog()
                    _plural = self.get_plural()
                    if _catalog:
                        catalog[code] = _catalog
                    if _plural:
                        plural[code] = _plural
                template = Engine().from_string(js_catalog_template)
                context = {
                    'catalog_str': json.dumps(catalog, sort_keys=True, indent=2),
                    'formats_str': json.dumps(formats, sort_keys=True, indent=2),
                    'plural': plural,
                }
                return template.render(Context(context))

        return InlineJavaScriptCatalog().render_to_str()
