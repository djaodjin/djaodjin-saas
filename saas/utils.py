# Copyright (c) 2022, DjaoDjin inc.
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

import datetime, inspect, random, re, sys, json

from django.core.exceptions import NON_FIELD_ERRORS
from django.core.files.storage import default_storage
from django.conf import settings as django_settings
from django.db import transaction, IntegrityError
from django.http.request import split_domain_port, validate_host
from django.template.defaultfilters import slugify
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.timezone import utc, get_current_timezone
from rest_framework.exceptions import ValidationError
from rest_framework.settings import api_settings
from pytz import timezone, UnknownTimeZoneError
from pytz.tzinfo import BaseTzInfo

from .compat import get_model_class, gettext_lazy as _, import_string, six


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
    if issubclass(type(tzone), BaseTzInfo):
        return tzone
    if tzone:
        try:
            return timezone(tzone)
        except UnknownTimeZoneError:
            pass
    return None


def convert_dates_to_utc(dates):
    return [date.astimezone(utc) for date in dates]


def as_timestamp(dtime_at=None):
    if not dtime_at:
        dtime_at = datetime_or_now()
    return int((
        dtime_at - datetime.datetime(1970, 1, 1, tzinfo=utc)).total_seconds())


def datetime_or_now(dtime_at=None, tzinfo=None):
    if not tzinfo:
        tzinfo = utc
    as_datetime = dtime_at
    if isinstance(dtime_at, six.string_types):
        as_datetime = parse_datetime(dtime_at)
        if not as_datetime:
            as_date = parse_date(dtime_at)
            if as_date:
                as_datetime = datetime.datetime.combine(
                    as_date, datetime.time.min)
    if not as_datetime:
        as_datetime = datetime.datetime.now(tz=tzinfo)
    if (as_datetime.tzinfo is None or
        as_datetime.tzinfo.utcoffset(as_datetime) is None):
        as_datetime = as_datetime.replace(tzinfo=tzinfo)
    return as_datetime


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


def full_name_natural_split(full_name, middle_initials=True):
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
    if middle_initials:
        mid_name = ""
        for middle_name in parts:
            if middle_name:
                mid_name += middle_name[0]
    else:
        mid_name = " ".join(parts)
    return first_name, mid_name, last_name


def generate_random_slug(length=40, prefix=None):
    """
    This function is used, for example, to create Coupon code mechanically
    when a customer pays for the subscriptions of an organization which
    does not yet exist in the database.
    """
    if prefix:
        length = length - len(prefix)
    # make sure the slug starts with a letter in case it is used as a resource
    # name (variable or database).
    suffix = random.choice("abcdef")
    suffix += "".join([random.choice("abcdef0123456789")
                      for val in range(length - 1)]) # Generated coupon codes
                             # are stored as ``Transaction.event_id`` with
                             # a 'cpn_' prefix. The total event_id must be less
                             # than 50 chars.
    if prefix:
        return str(prefix) + suffix
    return suffix


def get_organization_model():
    # delayed import so we can load ``OrganizationMixinBase`` in django.conf
    from . import settings #pylint:disable=import-outside-toplevel
    return get_model_class(settings.ORGANIZATION_MODEL, 'ORGANIZATION_MODEL')


def get_role_model():
    # delayed import so we can load ``OrganizationMixinBase`` in django.conf
    from . import settings #pylint:disable=import-outside-toplevel
    return get_model_class(settings.ROLE_MODEL, 'ROLE_MODEL')


def get_role_serializer():
    """
    Returns the role serializer model that is active in this project.
    """
    from . import settings #pylint:disable=import-outside-toplevel
    return import_string(settings.ROLE_SERIALIZER)


def get_user_serializer():
    """
    Returns the user serializer model that is active in this project.
    """
    from . import settings #pylint:disable=import-outside-toplevel
    return import_string(settings.USER_SERIALIZER)


def get_user_detail_serializer():
    """
    Returns the user serializer model that is active in this project.
    """
    from . import settings #pylint:disable=import-outside-toplevel
    return import_string(settings.USER_DETAIL_SERIALIZER)


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


def validate_redirect_url(next_url, sub=False, **kwargs):
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
    path = parts.path
    if sub:
        from . import settings #pylint:disable=import-outside-toplevel
        try:
            # We replace all ':slug/' by '%(slug)s/' so that we can further
            # create an instantiated url through Python string expansion.
            pat_kwargs = kwargs
            if 'profile' not in kwargs:
                # XXX deployutils is using :profile but djaoapp still generates
                #     :organization for the time being.
                profile = kwargs['organization']
                pat_kwargs = kwargs.copy()
                pat_kwargs.update({'profile': profile})
            path = re.sub(r':(%s)/' % settings.ACCT_REGEX,
                r'%(\1)s/', path) % pat_kwargs
        except KeyError:
            # We don't have all keys necessary. A safe defaults is to remove
            # them. Most likely a redirect URL is present to pick between
            # multiple choices.
            path = re.sub(r':(%s)/' % settings.ACCT_REGEX, '', path)
    return six.moves.urllib.parse.urlunparse(("", "", path,
        parts.params, parts.query, parts.fragment))


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
    field_names = None
    err_msg = str(err).splitlines().pop()
    # PostgreSQL unique constraint.
    look = re.match(
        r'DETAIL:\s+Key \(([a-z_]+(, [a-z_]+)*)\)=\(.*\) already exists\.',
        err_msg)
    if look:
        # XXX Do we need to include '.' in pattern as done later on?
        field_names = look.group(1).split(',')
    else:
        look = re.match(
          r'DETAIL:\s+Key \(lower\(([a-z_]+)::text\)\)=\(.*\) already exists\.',
            err_msg)
        if look:
            field_names = [look.group(1)]
        else:
            # SQLite unique constraint.
            look = re.match(r'UNIQUE constraint failed: '\
                r'(?P<cols>[a-z_]+\.[a-z_]+(, [a-z_]+\.[a-z_]+)*)', err_msg)
            if not look:
                # On CentOS 7, installed sqlite 3.7.17
                # returns differently-formatted error message.
                look = re.match(
                    r'column(s)? (?P<cols>[a-z_]+(\.[a-z_]+)?'\
                    r'(, [a-z_]+(\.[a-z_]+)?)*) (is|are) not unique', err_msg)
            if look:
                field_names = [field_name.split('.')[-1]
                    for field_name in look.group('cols').split(',')]
    if field_names:
        renamed_fields = []
        for field_name in field_names:
            if renames and field_name in renames:
                field_name = renames[field_name]
            renamed_fields += [field_name]
        # XXX retrieves `saas_coupon.code` duplicates
        field_name = renamed_fields[-1]
        raise ValidationError({field_name:
            _("This %(field)s is already taken.") % {'field': field_name}})
    raise err


def get_picture_storage(request, account=None, **kwargs):
    # delayed import so we can load ``OrganizationMixinBase`` in django.conf
    from . import settings #pylint:disable=import-outside-toplevel
    if settings.PICTURE_STORAGE_CALLABLE:
        try:
            return import_string(settings.PICTURE_STORAGE_CALLABLE)(
                request, account=account, **kwargs)
        except ImportError:
            pass
    return default_storage


# XXX same prototype as djaodjin-multitier.mixins.build_absolute_uri
def build_absolute_uri(request, location='/', provider=None, with_scheme=True):
    # delayed import so we can load ``OrganizationMixinBase`` in django.conf
    from . import settings #pylint:disable=import-outside-toplevel
    if settings.BUILD_ABSOLUTE_URI_CALLABLE:
        try:
            return import_string(
                settings.BUILD_ABSOLUTE_URI_CALLABLE)(request,
                    location=location, provider=provider,
                    with_scheme=with_scheme)
        except ImportError:
            pass
    if request:
        return request.build_absolute_uri(location)
    # If we don't have a `request` object, better to return a URL path
    # than throwing an error.
    return location


class CurrencyDataLoader:
    _currency_data = None

    @classmethod
    def load_currency_data(cls):
        if cls._currency_data is None:
            from . import settings #pylint:disable=import-outside-toplevel
            with open(settings.CURRENCY_JSON_PATH, 'r') as file:
                currency_list = json.load(file)
                cls._currency_data = {currency['cc']:
                    currency for currency in currency_list}
        return cls._currency_data

    @classmethod
    def get_currency_symbols(cls, currency_code):
        data = cls.load_currency_data()
        if data:
            currency = data.get(currency_code.upper())
            if currency:
                return currency['symbol']
        return None

    @classmethod
    def get_currency_choices(cls):
        data = cls.load_currency_data()
        if data:
            return [(code.lower(), code.lower()) for code in data.keys()]
        return []
