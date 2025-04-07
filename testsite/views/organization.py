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

from django import forms
from django.contrib.auth import get_user_model
from django.views.generic import ListView, FormView

from saas.compat import gettext_lazy as _
from saas.mixins import UserMixin
from saas.utils import get_organization_model


class OrganizationListView(ListView):

    model = get_organization_model()
    template_name = 'organization_list_index.html'


class UserForm(forms.ModelForm):
    """
    Form to update a ``User`` profile.
    """
    submit_title = _("Update")

    username = forms.SlugField(widget=forms.TextInput(
        attrs={'placeholder': _("Username")}),
        max_length=30, label=_("Username"),
        error_messages={'invalid': _("Username may only contain letters,"\
            " digits and -/_ characters. Spaces are not allowed.")})
    full_name = forms.CharField(widget=forms.TextInput(
        attrs={'placeholder': _("First and last names")}),
        max_length=254, label=_("Full name"))
    nick_name = forms.CharField(required=False, widget=forms.TextInput(
        attrs={'placeholder': _("Short casual name used to address the user")}),
        max_length=254, label=_("Nick name"))

    class Meta:
        model = get_user_model()
        fields = ['username', 'full_name', 'email']


class UserProfileView(UserMixin, FormView):

    form_class = UserForm
    template_name = 'accounts/profile.html'

    def get_initial(self):
        initial = super(UserProfileView, self).get_initial()
        if self.user:
            initial.update({
                'username': self.user.username,
                'full_name': self.user.get_full_name(),
                'email': self.user.email
            })
        return initial
