# Copyright (c) 2021, DjaoDjin inc.
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

from django.dispatch import Signal

#pylint: disable=invalid-name
organization_updated = Signal(
#    providing_args=['organization', 'changes', 'user']
)
plan_created = Signal(
#    providing_args=['plan']
)
plan_updated = Signal(
#    providing_args=['plan']
)
bank_updated = Signal(
#    providing_args=['organization', 'user']
)
card_updated = Signal(
#    providing_args=['organization', 'user', 'old_card', 'new_card']
)
charge_updated = Signal(
#    providing_args=['charge', 'user']
)
order_executed = Signal(
#    providing_args=['invoiced_items', 'user']
)
claim_code_generated = Signal(
#    providing_args=['subscriber', 'claim_code', 'user']
)
expires_soon = Signal(
#    providing_args=['subscription', 'nb_days']
)
card_expires_soon = Signal(
#    providing_args=['organization', 'nb_days']
)
subscription_upgrade = Signal(
#    providing_args=['subscription', 'nb_days']
)
payment_method_absent = Signal(
#    providing_args=['organization']
)
user_invited = Signal(
#    providing_args=['user', 'invited_by']
)
processor_setup_error = Signal(
#    providing_args=['provider', 'error_message', 'customer']
)
renewal_charge_failed = Signal(
#    providing_args=['invoiced_items', 'total_price', 'final_notice']
)
role_grant_accepted = Signal(
#    providing_args=['role', 'grant_key']
)
role_grant_created = Signal(
#    providing_args=['role', 'reason']
)
# There is no `role_request_accepted` because a `role_grant_created`
# will already be triggered when the request is accepted.
role_request_created = Signal(
#    providing_args=['role', 'reason']
)
subscription_grant_accepted = Signal(
#    providing_args=['subscription', 'grant_key']
)
subscription_grant_created = Signal(
#    providing_args=['subscription', 'reason', 'invite']
)
subscription_request_accepted = Signal(
#    providing_args=['subscription', 'request_key']
)
subscription_request_created = Signal(
#    providing_args=['subscription', 'reason']
)
weekly_sales_report_created = Signal(
#    providing_args=['provider', 'dates', 'data']
)
