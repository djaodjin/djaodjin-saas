# Copyright (c) 2025, DjaoDjin inc.
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

import datetime

from django.utils.dateparse import parse_date, parse_datetime

from .compat import six, timezone_or_utc


def as_timestamp(dtime_at=None):
    if not dtime_at:
        dtime_at = datetime_or_now()
    return int((
        dtime_at - datetime.datetime(1970, 1, 1,
            tzinfo=timezone_or_utc())).total_seconds())


def datetime_or_now(dtime_at=None, tzinfo=None):
    if not tzinfo:
        tzinfo = timezone_or_utc()
    as_datetime = dtime_at
    if isinstance(dtime_at, six.string_types):
        as_datetime = parse_datetime(dtime_at)
        if not as_datetime:
            as_date = parse_date(dtime_at)
            if as_date:
                as_datetime = datetime.datetime.combine(
                    as_date, datetime.time.min)
    elif (not isinstance(dtime_at, datetime.datetime) and
          isinstance(dtime_at, datetime.date)):
        as_datetime = datetime.datetime.combine(
            dtime_at, datetime.time.min)
    if not as_datetime:
        as_datetime = datetime.datetime.now(tz=tzinfo)
    if (as_datetime.tzinfo is None or
        as_datetime.tzinfo.utcoffset(as_datetime) is None):
        as_datetime = as_datetime.replace(tzinfo=tzinfo)
    return as_datetime


def full_name_natural_parts(full_name, middle_initials=False):
    """
    This function splits a full name into a natural first name, last name
    and middle names, or middle initials when `middle_initials` is `True`.
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


def full_name_natural_split(full_name):
    """
    This function splits a full name into a natural first name and last name.
    As no characters are dropped, the middle names are attached to the last
    name.

    If you are looking for a function that splits the middle name in its
    own right, look at `full_name_natural_parts`.
    """
    first_name, mid_names, last_name = full_name_natural_parts(full_name)
    return first_name, ' '.join([
        mid_names if mid_names else "",
        last_name if last_name else ""]).strip()


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
