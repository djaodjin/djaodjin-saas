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

from django.core.urlresolvers import reverse
from django.views.generic import ListView

from ..models import Organization
from ..mixins import UserMixin, ProviderMixin


class ProductListView(UserMixin, ProviderMixin, ListView):
    """List of organizations the request.user is a manager
    or contributor for."""
    # XXX We use ``OrganizationMixin`` so that urls.pricing is defined.

    paginate_by = 10
    template_name = 'saas/managed_list.html'

    def get_queryset(self):
        return Organization.objects.accessible_by(self.user)

    def get_context_data(self, **kwargs):
        context = super(ProductListView, self).get_context_data(**kwargs)
        context.update({'organizations': context['object_list'],
                        # XXX include users/base.html
                        'object': self.user})
        user_urls = {
            'products': reverse('saas_user_product_list', args=(self.user,)),
        }
        if 'urls' in context:
            if 'user' in context['urls']:
                context['urls']['user'].update(user_urls)
            else:
                context['urls'].update({'user': user_urls})
        else:
            context.update({'urls': {'user': user_urls}})
        return context



