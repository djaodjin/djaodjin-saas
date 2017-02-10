# Copyright (c) 2017, DjaoDjin inc.
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

import datetime, inspect, random, sys

from django.conf import settings as django_settings
from django.db import transaction, IntegrityError
from django.http.request import split_domain_port, validate_host
from django.template.defaultfilters import slugify
from django.utils import six
from django.utils.timezone import utc, get_current_timezone
from rest_framework.exceptions import ValidationError


class SlugTitleMixin(object):
    """
    Generate a unique slug from title on ``save()`` when none is specified.
    """
    def save(self, force_insert=False, force_update=False,
             using=None, update_fields=None):
        if self.slug: #pylint:disable=access-member-before-definition
            # serializer will set created slug to '' instead of None.
            return super(SlugTitleMixin, self).save(
                force_insert=force_insert, force_update=force_update,
                using=using, update_fields=update_fields)
        max_length = self._meta.get_field('slug').max_length
        slug_base = slugify(self.title)
        if len(slug_base) > max_length:
            slug_base = slug_base[:max_length]
        self.slug = slug_base
        for _ in range(1, 10):
            try:
                with transaction.atomic():
                    return super(SlugTitleMixin, self).save(
                        force_insert=force_insert, force_update=force_update,
                        using=using, update_fields=update_fields)
            except IntegrityError as err:
                if 'uniq' not in str(err).lower():
                    raise
                suffix = '-%s' % "".join([random.choice("abcdef0123456789")
                    for _ in range(7)])
                if len(slug_base) + len(suffix) > max_length:
                    self.slug = slug_base[:(max_length - len(suffix))] + suffix
                else:
                    self.slug = slug_base + suffix
        raise ValidationError({'detail':
            "Unable to create a unique URL slug from title '%s'" % self.title})


def datetime_or_now(dtime_at=None):
    if not dtime_at:
        return datetime.datetime.utcnow().replace(tzinfo=utc)
    if isinstance(dtime_at, six.string_types):
        dtime_at = datetime.datetime.strptime(dtime_at, "%Y-%m-%dT%H:%M:%S")
    if dtime_at.tzinfo is None:
        dtime_at = dtime_at.replace(tzinfo=utc)
    return dtime_at


def datetime_to_utctimestamp(dtime_at, epoch=None):
    if epoch is None:
        epoch = datetime.datetime(1970, 1, 1).replace(tzinfo=utc)
    if dtime_at is None:
        dtime_at = epoch
    diff = dtime_at - epoch
    return int(diff.total_seconds())


def extract_full_exception_stack(err):
    tbk = sys.exc_info()[2]
    message = str(err) + '\nTraceback (most recent call last):'
    for item in reversed(inspect.getouterframes(tbk.tb_frame)[1:]):
        message += ' File "{1}", line {2}, in {3}\n'.format(*item)
        for line in item[4]:
            message += ' ' + line.lstrip()
    for item in inspect.getinnerframes(tbk):
        message += ' File "{1}", line {2}, in {3}\n'.format(*item)
        for line in item[4]:
            message += ' ' + line.lstrip()
    message += '%s: %s' % (err.__class__, err)
    return message


def generate_random_slug(prefix=None):
    """
    This function is used, for example, to create Coupon code mechanically
    when a customer pays for the subscriptions of an organization which
    does not yet exist in the database.
    """
    suffix = "".join([random.choice("abcdefghijklmnopqrstuvwxyz0123456789-")
                      for _ in range(40)]) # Generated coupon codes are stored
                             # as ``Transaction.event_id`` we a 'cpn_' prefix.
                             # The total event_id must be less than 50 chars.
    if prefix:
        return str(prefix) + suffix
    return suffix


def get_organization_model():
    # delayed import so we can load ``OrganizationMixinBase`` in django.conf
    from . import settings
    from .compat import get_model_class
    return get_model_class(settings.ORGANIZATION_MODEL, 'ORGANIZATION_MODEL')

def get_role_model():
    # delayed import so we can load ``OrganizationMixinBase`` in django.conf
    from . import settings
    from .compat import get_model_class
    return get_model_class(settings.ROLE_RELATION, 'ROLE_RELATION')


def normalize_role_name(role_name):
    if role_name.endswith('s'):
        role_name = role_name[:-1]
    return role_name


def start_of_day(dtime_at=None):
    """
    Returns the local (user timezone) start of day, that's,
    time 00:00:00 for a given datetime
    """
    dtime_at = datetime_or_now(dtime_at)
    return datetime.datetime(dtime_at.year, dtime_at.month,
        dtime_at.day, tzinfo=get_current_timezone())


def validate_redirect_url(next_url):
    """
    Returns the next_url path if next_url matches allowed hosts.
    """
    # This method is copy/pasted from signup.auth so we donot need
    # to add djaodjin-signup as a prerequisites. It is possible
    # the functionality has already moved into Django proper.
    if not next_url:
        return None
    parts = six.moves.urllib.parse.urlparse(next_url)
    if parts.netloc:
        domain, _ = split_domain_port(parts.netloc)
        allowed_hosts = ['*'] if django_settings.DEBUG \
            else django_settings.ALLOWED_HOSTS
        if not (domain and validate_host(domain, allowed_hosts)):
            return None
    return parts.path


def utctimestamp_to_datetime(timestamp):
    return datetime_or_now(datetime.datetime.utcfromtimestamp(timestamp))
