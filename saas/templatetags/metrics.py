# Copyright (c) 2014, Fortylines LLC
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.

from datetime import datetime, timedelta

from django import template

from saas.compat import User

register = template.Library()


@register.filter()
def is_incomplete_month(date):
    return ((isinstance(date, basestring) and not date.endswith('01'))
        or (isinstance(date, datetime) and date.day != 1))


@register.filter()
def monthly_caption(last_date):
    """returns a formatted caption describing the period whose end
    date is *last_date*."""
    if last_date.day == 1:
        prev = last_date - timedelta(days=2) # more than one day to make sure
        return datetime.strftime(prev, "%b'%y")
    else:
        return datetime.strftime(last_date, "%b'%y") + "*"


@register.filter()
def personal(organization):
    """
    Returns ``True`` if the organization is undistinguishable from a user.
    """
    if organization:
        return User.objects.filter(username=organization).exists()
    return False


@register.filter()
def products(organization):
    """
    Returns a list of distinct providers (i.e. ``Organization``) from
    the plans the *organization* is subscribed to.
    """
    if organization:
        # We don't use QuerySet.distinct('organization') because the SQLite
        # backend does not support DISTINCT ON queries.
        return organization.subscriptions.all().values(
            'organization__name').distinct()
    return []

