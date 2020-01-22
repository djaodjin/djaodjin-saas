# Copyright (c) 2020, DjaoDjin inc.
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

from django.views.generic import TemplateView

from ..compat import reverse
from ..mixins import UserMixin
from ..utils import update_context_urls


class ProductListView(UserMixin, TemplateView):
    """
    List of organizations a ``:user`` has a role with.

    Template:

    To edit the layout of this page, create a local \
    ``saas/users/roles.html`` (`example <https://github.com/djaodjin\
/djaodjin-saas/tree/master/saas/templates/saas/users/roles.html>`__).
    You should insure the page will call back the
    :ref:`/api/users/:user/roles/ <api_accessibles>`
    API end point to fetch the set of organization accessible by the user.

    Template context:
      - ``user`` The organization object users have permissions to.
      - ``request`` The HTTP request object
    """
    # XXX We use ``OrganizationMixin`` so that urls.pricing is defined.

    template_name = 'saas/users/roles.html'

    def get_context_data(self, **kwargs):
        context = super(ProductListView, self).get_context_data(**kwargs)
        urls = {
            'api_candidates': reverse('saas_api_search_profiles'),
            'user': {
                'api_accessibles': reverse(
                    'saas_api_accessibles', args=(self.user,)),
                'api_profile_create': reverse(
                    'saas_api_user_profiles', args=(self.user,)),
        }}
        update_context_urls(context, urls)
        return context
