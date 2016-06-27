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

from django.contrib import admin
from django import forms

from .models import (Agreement, CartItem, Charge, ChargeItem, Coupon,
    Organization, Role, RoleDescription, Plan, Signature, Subscription,
    Transaction)

admin.site.register(Agreement)
admin.site.register(CartItem)
admin.site.register(Charge)
admin.site.register(ChargeItem)
admin.site.register(Coupon)
admin.site.register(Organization)
admin.site.register(Plan)
admin.site.register(Role)
admin.site.register(RoleDescription)
admin.site.register(Signature)
admin.site.register(Subscription)
admin.site.register(Transaction)


class RoleForm(forms.ModelForm):

    name = forms.ChoiceField(
        choices=[('manager', 'manager'), ('contributor', 'contributor')])

    class Meta:
        model = Role
        fields = ('name', 'organization', 'user',
            'request_key', 'grant_key')


class RoleAdmin(admin.ModelAdmin):
    form = RoleForm

admin.site.register(Role, RoleAdmin)
