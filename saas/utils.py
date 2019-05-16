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

import datetime, inspect, random, re, sys

from django.core.exceptions import NON_FIELD_ERRORS
from django.core.files.storage import default_storage
from django.conf import settings as django_settings
from django.db import transaction, IntegrityError
from django.http.request import split_domain_port, validate_host
from django.template.defaultfilters import slugify
from django.utils import six
from django.utils.dateparse import parse_datetime
from django.utils.timezone import utc, get_current_timezone
from django.utils.translation import ugettext_lazy as _
from rest_framework.exceptions import ValidationError
from rest_framework.settings import api_settings
from pytz import timezone, UnknownTimeZoneError
from pytz.tzinfo import DstTzInfo
from .compat import get_model_class, import_string


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
                suffix = '-%s' % generate_random_slug(length=7)
                if len(slug_base) + len(suffix) > max_length:
                    self.slug = slug_base[:(max_length - len(suffix))] + suffix
                else:
                    self.slug = slug_base + suffix
        raise ValidationError({'detail':
            "Unable to create a unique URL slug from title '%s'" % self.title})


def parse_tz(tzone):
    if issubclass(type(tzone), DstTzInfo):
        return tzone
    if tzone:
        try:
            return timezone(tzone)
        except UnknownTimeZoneError:
            pass
    return None


def convert_dates_to_utc(dates):
    return [date.astimezone(utc) for date in dates]


def datetime_or_now(dtime_at=None):
    if isinstance(dtime_at, six.string_types):
        dtime_at = parse_datetime(dtime_at)
    if not dtime_at:
        dtime_at = datetime.datetime.utcnow().replace(tzinfo=utc)
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


def full_name_natural_split(full_name):
    """
    This function splits a full name into a natural first name, last name
    and middle initials.
    """
    parts = full_name.strip().split(' ')
    first_name = ""
    if parts:
        first_name = parts.pop(0)
    if first_name.lower() == "el" and parts:
        first_name += " " + parts.pop(0)
    last_name = ""
    if parts:
        last_name = parts.pop()
    if (last_name.lower() == 'i' or last_name.lower() == 'ii'
        or last_name.lower() == 'iii' and parts):
        last_name = parts.pop() + " " + last_name
    middle_initials = ""
    for middle_name in parts:
        if middle_name:
            middle_initials += middle_name[0]
    return first_name, middle_initials, last_name


def generate_random_slug(length=40, prefix=None):
    """
    This function is used, for example, to create Coupon code mechanically
    when a customer pays for the subscriptions of an organization which
    does not yet exist in the database.
    """
    if prefix:
        length = length - len(prefix)
    suffix = "".join([random.choice("abcdef0123456789")
                      for val in range(length)]) # Generated coupon codes are
                             # stored as ``Transaction.event_id`` we a 'cpn_'
                             # prefix. The total event_id must be less than 50
                             # chars.
    if prefix:
        return str(prefix) + suffix
    return suffix


def get_organization_model():
    # delayed import so we can load ``OrganizationMixinBase`` in django.conf
    from . import settings
    return get_model_class(settings.ORGANIZATION_MODEL, 'ORGANIZATION_MODEL')


def get_role_model():
    # delayed import so we can load ``OrganizationMixinBase`` in django.conf
    from . import settings
    return get_model_class(settings.ROLE_RELATION, 'ROLE_RELATION')


def start_of_day(dtime_at=None):
    """
    Returns the local (user timezone) start of day, that's,
    time 00:00:00 for a given datetime
    """
    dtime_at = datetime_or_now(dtime_at)
    start = datetime.datetime(dtime_at.year, dtime_at.month,
        dtime_at.day)
    tz_ob = get_current_timezone()
    if tz_ob:
        start = tz_ob.localize(start)
    return start


def update_context_urls(context, urls):
    if 'urls' in context:
        for key, val in six.iteritems(urls):
            if key in context['urls']:
                if isinstance(val, dict):
                    context['urls'][key].update(val)
                else:
                    # Because organization_create url is added in this mixin
                    # and in ``OrganizationRedirectView``.
                    context['urls'][key] = val
            else:
                context['urls'].update({key: val})
    else:
        context.update({'urls': urls})
    return context


def utctimestamp_to_datetime(timestamp):
    return datetime_or_now(datetime.datetime.utcfromtimestamp(timestamp))


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


def update_db_row(instance, form):
    """
    Updates the record in the underlying database, or adds a validation
    error in the form. When an error is added, the form is returned otherwise
    this function returns `None`.
    """
    try:
        try:
            instance.save()
        except IntegrityError as err:
            handle_uniq_error(err)
    except ValidationError as err:
        fill_form_errors(form, err)
        return form
    return None


def fill_form_errors(form, err):
    """
    Fill a Django form from DRF ValidationError exceptions.
    """
    if isinstance(err.detail, dict):
        for field, msg in six.iteritems(err.detail):
            if field in form.fields:
                form.add_error(field, msg)
            elif field == api_settings.NON_FIELD_ERRORS_KEY:
                form.add_error(NON_FIELD_ERRORS, msg)
            else:
                form.add_error(NON_FIELD_ERRORS,
                    _("No field '%(field)s': %(msg)s" % {
                    'field': field, 'msg': msg}))


def handle_uniq_error(err, renames=None):
    """
    Will raise a ``ValidationError`` with the appropriate error message.
    """
    field_name = None
    err_msg = str(err).splitlines().pop()
    # PostgreSQL unique constraint.
    look = re.match(
        r'DETAIL:\s+Key \(([a-z_]+)\)=\(.*\) already exists\.', err_msg)
    if look:
        field_name = look.group(1)
    else:
        look = re.match(
          r'DETAIL:\s+Key \(lower\(([a-z_]+)::text\)\)=\(.*\) already exists\.',
            err_msg)
        if look:
            field_name = look.group(1)
        else:
            # SQLite unique constraint.
            look = re.match(
                r'UNIQUE constraint failed: [a-z_]+\.([a-z_]+)', err_msg)
            if look:
                field_name = look.group(1)
            else:
                # On CentOS 7, installed sqlite 3.7.17
                # returns differently-formatted error message.
                look = re.match(
                    r'column ([a-z_]+) is not unique', err_msg)
                if look:
                    field_name = look.group(1)
    if field_name:
        if renames and field_name in renames:
            field_name = renames[field_name]
        raise ValidationError({field_name:
            _("This %(field)s is already taken.") % {'field': field_name}})
    raise err


def get_picture_storage():
    # delayed import so we can load ``OrganizationMixinBase`` in django.conf
    from . import settings
    if settings.PICTURE_STORAGE_CALLABLE:
        try:
            return import_string(settings.PICTURE_STORAGE_CALLABLE)()
        except ImportError:
            pass
    return default_storage


# XXX same prototype as djaodjin-multitier.mixins.build_absolute_uri
def build_absolute_uri(request, location='/', provider=None, with_scheme=True):
    # delayed import so we can load ``OrganizationMixinBase`` in django.conf
    from . import settings
    if settings.BUILD_ABSOLUTE_URI_CALLABLE:
        try:
            return import_string(
                settings.BUILD_ABSOLUTE_URI_CALLABLE)(request,
                    location=location, provider=provider,
                    with_scheme=with_scheme)
        except ImportError:
            pass
    return request.build_absolute_uri(location)


def is_broker(organization):
    """
    Returns ``True`` if the organization is the hosting platform
    for the service.
    """
    # delayed import so we can load ``OrganizationMixinBase`` in django.conf
    from . import settings
    from .models import get_broker
    # We do a string compare here because both ``Organization`` might come
    # from a different db. That is if the organization parameter is not
    # a unicode string itself.
    organization_slug = ''
    if isinstance(organization, six.string_types):
        organization_slug = organization
    elif organization:
        organization_slug = organization.slug
    if settings.IS_BROKER_CALLABLE:
        return import_string(settings.IS_BROKER_CALLABLE)(organization_slug)
    return get_broker().slug == organization_slug
