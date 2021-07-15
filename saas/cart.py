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
#pylint:disable=too-many-lines
from __future__ import unicode_literals

from django.db import transaction
from rest_framework.generics import get_object_or_404

from .compat import is_authenticated
from .models import CartItem, Coupon, Plan, UseCharge


def cart_insert_item(request, **kwargs):
    """
    Insert an item in the `request.user`'s cart whether the user is
    authenticated (`CartItem` in database) or not (HTTP cookies).
    """
    #pylint: disable=too-many-statements,too-many-nested-blocks
    #pylint: disable=too-many-locals
    created = False
    inserted_item = None
    template_item = None
    invoice_key = kwargs.get('invoice_key')
    sync_on = kwargs.get('sync_on', '')
    option = kwargs.get('option', 0)
    email = kwargs.get('email', '')
    plan = kwargs['plan']
    if not isinstance(plan, Plan):
        plan = get_object_or_404(Plan.objects.all(), slug=plan)
    use = kwargs.get('use', None)
    if use and not isinstance(use, UseCharge):
        use = get_object_or_404(UseCharge.objects.filter(
            plan=plan), slug=use)
    if is_authenticated(request):
        # If the user is authenticated, we just create the cart items
        # into the database.
        queryset = CartItem.objects.get_cart(
            request.user, plan=plan).order_by('-sync_on')
        if queryset.exists():
            template_item = queryset.first()
        if template_item:
            created = False
            inserted_item = template_item
            if sync_on:
                account = queryset.filter(email=email)
                if account.exists():
                    inserted_item = template_item = account.first()

                template_option = template_item.option
                if option > 0:
                    template_option = option
                # Bulk buyer subscribes someone else than request.user
                if template_item.sync_on:
                    if sync_on != template_item.sync_on:
                        # Copy/Replace in template CartItem
                        created = True
                        inserted_item = CartItem.objects.create(
                            user=request.user,
                            plan=template_item.plan,
                            use=template_item.use,
                            coupon=template_item.coupon,
                            option=template_option,
                            full_name=kwargs.get('full_name', ''),
                            sync_on=sync_on,
                            email=email,
                            claim_code=invoice_key)
                else:
                    # Use template CartItem
                    inserted_item.full_name = kwargs.get('full_name', '')
                    inserted_item.option = template_option
                    inserted_item.sync_on = sync_on
                    inserted_item.email = email
                    inserted_item.save()
            else:
                # Use template CartItem
                inserted_item.full_name = kwargs.get('full_name', '')
                inserted_item.option = option
                inserted_item.save()
        else:
            # New CartItem
            created = True
            item_queryset = CartItem.objects.get_cart(user=request.user,
                plan=plan, sync_on=sync_on)
            # TODO this conditional is not necessary: at this point
            # we have already checked that there is no such CartItem, right?
            if item_queryset.exists():
                inserted_item = item_queryset.get()
            else:
                redeemed = request.session.get('redeemed', None)
                if redeemed:
                    redeemed = Coupon.objects.active(
                        plan.organization, redeemed).first()
                inserted_item = CartItem.objects.create(
                    plan=plan, use=use, coupon=redeemed,
                    user=request.user,
                    option=option,
                    full_name=kwargs.get('full_name', ''),
                    sync_on=sync_on, claim_code=invoice_key)

    else:
        # We have an anonymous user so let's play some tricks with
        # the session data.
        cart_items = []
        if 'cart_items' in request.session:
            cart_items = request.session['cart_items']
        for item in cart_items:
            if item['plan'] == str(plan):
                if not template_item:
                    template_item = item
                elif ('sync_on' in template_item and 'sync_on' in item
                  and len(template_item['sync_on']) > len(item['sync_on'])):
                    template_item = item
        if template_item:
            created = False
            inserted_item = template_item
            if sync_on:
                # Bulk buyer subscribes someone else than request.user
                if template_item.sync_on:
                    if sync_on != template_item.sync_on:
                        # (anonymous) Copy/Replace in template item
                        created = True
                        cart_items += [{
                            'plan': template_item['plan'],
                            'use': template_item['use'],
                            'option': template_item['option'],
                            'full_name': kwargs.get('full_name', ''),
                            'sync_on': sync_on,
                            'email': email,
                            'invoice_key': invoice_key}]
                else:
                    # (anonymous) Use template item
                    inserted_item['full_name'] = kwargs.get(
                        'full_name', '')
                    inserted_item['sync_on'] = sync_on
                    inserted_item['email'] = email
        else:
            # (anonymous) New item
            created = True
            inserted_item = {
                'plan': str(plan),
                'use': str(use),
                'option': kwargs.get('option', 0),
                'full_name': kwargs.get('full_name', ''),
                'sync_on': sync_on,
                'email': email,
                'invoice_key': invoice_key
            }
            cart_items += [inserted_item]
        request.session['cart_items'] = cart_items
    return inserted_item, created


def session_cart_to_database(request):
    """
    Transfer all the items in the cart stored in the session into proper
    records in the database.
    """
    #pylint:disable=too-many-statements
    claim_code = request.GET.get('code', None)
    if claim_code:
        with transaction.atomic():
            cart_items = CartItem.objects.by_claim_code(claim_code)
            for cart_item in cart_items:
                cart_item.user = request.user
                cart_item.save()
    if 'cart_items' in request.session:
        with transaction.atomic():
            cart_items = CartItem.objects.get_cart(
                user=request.user).select_related('plan').order_by(
                'plan', 'full_name', 'email', 'sync_on')
            for item in request.session['cart_items']:
                plan_slug = item.get('plan')
                if not plan_slug:
                    continue
                coupon = item.get('coupon', None)
                option = item.get('option', 0)
                full_name = item.get('full_name', '')
                sync_on = item.get('sync_on', '')
                email = item.get('email', '')
                # Merging items in the request session
                # with items in the database.
                candidate = None
                for cart_item in cart_items:
                    if plan_slug != cart_item.plan.slug:
                        continue
                    if (full_name and (not cart_item.full_name or
                        full_name != cart_item.full_name)):
                        continue
                    if (email and (not cart_item.email or
                        email != cart_item.email)):
                        continue
                    if (sync_on and (not cart_item.sync_on or
                        sync_on != cart_item.sync_on)):
                        continue
                    # We found a `CartItem` in the database that was can be
                    # further constrained by the cookie session item.
                    candidate = cart_item
                    break
                # if the item is already in the cart, it is OK to forget about
                # any additional count of it. We are just going to constraint
                # the available one further.
                if candidate:
                    updated = False
                    if coupon and not candidate.coupon:
                        candidate.coupon = coupon
                        updated = True
                    if option and not candidate.option:
                        candidate.option = option
                        updated = True
                    if full_name and not candidate.full_name:
                        candidate.full_name = full_name
                        updated = True
                    if sync_on and not candidate.sync_on:
                        candidate.sync_on = sync_on
                        updated = True
                    if email and not candidate.email:
                        candidate.email = email
                        updated = True
                    if updated:
                        candidate.save()
                else:
                    plan = get_object_or_404(Plan.objects.all(), slug=plan_slug)
                    CartItem.objects.create(
                        user=request.user, plan=plan,
                        full_name=full_name, email=email, sync_on=sync_on,
                        coupon=coupon, option=option)
            del request.session['cart_items']
    redeemed = request.session.get('redeemed', None)
    if redeemed:
        # When the user has selected items while anonymous, this step
        # could be folded into the previous transaction. None-the-less
        # plain and stupid is best here. We apply redeemed coupons
        # either way (anonymous or not).
        with transaction.atomic():
            CartItem.objects.redeem(request.user, redeemed)
            del request.session['redeemed']
