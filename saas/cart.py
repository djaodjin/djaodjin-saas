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
from django.db.models import Q
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
    invoice_key = kwargs.get('invoice_key')
    sync_on = kwargs.get('sync_on', '')
    option = kwargs.get('option', 0)
    full_name = kwargs.get('full_name', '')
    plan = kwargs['plan']
    if not isinstance(plan, Plan):
        plan = get_object_or_404(Plan.objects.all(), slug=plan)
    use = kwargs.get('use', None)
    if use and not isinstance(use, UseCharge):
        use = get_object_or_404(UseCharge.objects.filter(plan=plan), slug=use)
    redeemed = request.session.get('redeemed', None)
    if redeemed:
        redeemed = Coupon.objects.active(
            plan.organization, redeemed, plan=plan).first()

    if is_authenticated(request):
        # If the user is authenticated, we just create the cart items
        # into the database.
        template_item = None
        queryset = CartItem.objects.get_cart(
            request.user, plan=plan).order_by('-sync_on')
        template_item = queryset.first()
        if template_item:
            # Can we find a better template?
            filter_args = None
            if sync_on:
                if filter_args:
                    filter_args |= Q(sync_on=sync_on)
                else:
                    filter_args = Q(sync_on=sync_on)
            if option:
                if filter_args:
                    filter_args |= Q(option=option)
                else:
                    filter_args = Q(option=option)
            if use:
                if filter_args:
                    filter_args |= Q(use=use)
                else:
                    filter_args = Q(use=use)
            if filter_args:
                better_template_item = queryset.filter(filter_args).order_by(
                    'sync_on', 'option', 'use').first()
                if better_template_item:
                    template_item = better_template_item
            # Merge default values
            if not sync_on:
                sync_on = template_item.sync_on
            if not option:
                option = template_item.option
            if not use:
                use = template_item.use
            # Can we use that template?
            if sync_on:
                if template_item.sync_on and template_item.sync_on != sync_on:
                    # conflicting sync_on. we cannot use the template.
                    template_item = None
            if template_item and option:
                if template_item.option and template_item.option != option:
                    # conflicting option. we cannot use the template.
                    template_item = None
            if template_item and use:
                if template_item.use and template_item.use != use:
                    # conflicting use. we cannot use the template.
                    template_item = None
            if template_item:
                # There is no conflict. We can use the template.
                if sync_on and not template_item.sync_on:
                    template_item.sync_on = sync_on
                if option and not template_item.option:
                    template_item.option = option
                if use and not template_item.use:
                    template_item.use = use
                if full_name:
                    template_item.full_name = full_name
                if not template_item.coupon:
                    template_item.coupon = redeemed
                template_item.save()
                inserted_item = template_item
        if not inserted_item:
            # New CartItem
            created = True
            inserted_item = CartItem.objects.create(
                plan=plan,
                use=use,
                coupon=redeemed,
                user=request.user,
                option=option,
                full_name=full_name,
                sync_on=sync_on,
                claim_code=invoice_key)
    else:
        # We have an anonymous user so let's play some tricks with
        # the session data.
        template_item = {}
        cart_items = []
        if 'cart_items' in request.session:
            cart_items = request.session['cart_items']
        # Can we find a template?
        for item in cart_items:
            if item['plan'] == str(plan):
                if not template_item:
                    template_item = item
                    continue
                if sync_on:
                    item_sync_on = item.get('sync_on')
                    if item_sync_on and item_sync_on == sync_on:
                        if not template_item:
                            template_item = item
                            continue
                        if template_item.get('sync_on') != sync_on:
                            # The item matches on sync_on but the template
                            # does not.
                            template_item = item
                            continue
                        # We have a template_item with sync_on. Let's see
                        # if we find a better candidate.
                        if option:
                            item_option = item.get('option')
                            if item_option and item_option == option:
                                if not template_item:
                                    template_item = item
                                    continue
                                if template_item.get('option') != option:
                                    template_item = item
                                    continue
                                if use:
                                    item_use = item.get('use')
                                    if item_use and item_use == use:
                                        if not template_item:
                                            template_item = item
                                            continue
                                        if template_item.get('use') != use:
                                            template_item = item
                                            continue
                    if (template_item and
                        template_item.get('sync_on') == sync_on):
                        # We already have a template matching on `sync_on`.
                        continue
                # Couldn't match on `sync_on`. next is `option`.
                if option:
                    item_option = item.get('option')
                    if item_option and item_option == option:
                        if not template_item:
                            template_item = item
                            continue

                        if template_item.get('option') != option:
                            template_item = item
                            continue
                        if use:
                            item_use = item.get('use')
                            if item_use and item_use == use:
                                if not template_item:
                                    template_item = item
                                    continue
                                if template_item.get('use') != use:
                                    template_item = item
                                    continue
                    if (template_item and
                        template_item.get('option') == option):
                        # We already have a template matching on `sync_on`
                        # or `option`.
                        continue
                # Couldn't match on `sync_on` not `option`. next is `use`.
                if use:
                    item_use = item.get('use')
                    if item_use and item_use == use:
                        if not template_item:
                            template_item = item
                            continue
                        if template_item.get('use') != use:
                            template_item = item
                            continue

        if template_item:
            # Merge default values
            if not sync_on:
                sync_on = template_item.get('sync_on')
            if not option:
                option = template_item.get('option')
            if not use:
                use = template_item.get('use')
            # Can we use that template?
            if sync_on:
                template_sync_on = template_item.get('sync_on')
                if template_sync_on and template_sync_on != sync_on:
                    # conflicting sync_on. we cannot use the template.
                    template_item = None
            if template_item and option:
                template_option = template_item.get('option')
                if template_option and template_option != option:
                    # conflicting option. we cannot use the template.
                    template_item = None
            if template_item and use:
                template_use = template_item.get('use')
                if template_use and template_use != use:
                    # conflicting use. we cannot use the template.
                    template_item = None
            if template_item:
                # There is no conflict. We can use the template.
                if sync_on and not template_item.get('sync_on'):
                    template_item.update({'sync_on': sync_on})
                if option and not template_item.get('option'):
                    template_item.update({'option': option})
                if use and not template_item.get('use'):
                    template_item.update({'use': str(use)})
                if full_name:
                    template_item.update({'full_name': full_name})
                if not template_item.get('coupon') and redeemed:
                    template_item.update({'coupon': str(redeemed)})
                inserted_item = template_item
        if not inserted_item:
            # (anonymous) New item
            created = True
            inserted_item = {
                'plan': str(plan),
                'use': str(use),
                'option': option,
                'full_name': full_name,
                'sync_on': sync_on,
                'invoice_key': invoice_key
            }
            if redeemed:
                inserted_item.update({'coupon': str(redeemed)})
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
