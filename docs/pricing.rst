Pricing models
==============

Per-period pricing
------------------

This is the simplest form of subscription pricing. The subscriber pays a fixed
amount every single period (ex: $29/month). Setting up a per-period pricing
consists of creating a ``Plan`` with a ``period`` (``HOURLY``, ``DAILY``,
``WEEKLY``, ``MONTHLY``, ``YEARLY``) and a positive ``period_amount``.

Example fixtures for a $29/month::

    {
        "fields": {
            "slug": "indie",
            "created_at": "2019-01-01T00:00:00-00:00",
            "title": "Indie",
            "organization": 2,
            "is_active": 1.
            "period_amount": 2900,
            "period_type": 4
        },
        "model": "saas.Plan", "pk": 1
    }

The ``organization`` field is set to reference the plan provider; here
``Organization`` with ``pk == 2``. The plan is also marked to be available
on the pricing page (``is_active == 1``) such that user can subscribe
to the plan.
The ``period_amount`` is to set as an integer amount of cents, ``2900`` in this
case, while the ``period_type`` is set to ``4`` which is the enum value for
``Plan.MONTHLY``.

On the initial payment, when a user subscribes to the plan through the checkout
workflow, ``Organization.checkout`` will be called to create the initial charge
and the ``Subscription`` record.
Later on whenever the subscription is about to expire, the renewals management
command will call ``extend_subscriptions`` to extend the subscription by one
period, then call ``create_charges_for_balance`` to charge the period amount
to the card on file.


Per-period pricing with setup fee
---------------------------------

It is sometimes necessary to charge a one-time setup fee, maybe because
a human needs to be involved to setup a physical space (in case of a co-working
office) or send a device (in case of an IoT service).

Example fixtures for a $29/month + a one-time $10 setup fee::

    {
        "fields": {
            "slug": "indie",
            "created_at": "2019-01-01T00:00:00-00:00",
            "title": "Indie",
            "organization": 2,
            "is_active": 1,
            "period_amount": 2900,
            "period_type": 4,
            **"setup_amount": 1000**
        },
        "model": "saas.Plan", "pk": 1
    }

The ``setup_amount`` (in cents) is automatically added as a one-time charge
on the initial payment.


Per-period pricing with custom periods
--------------------------------------

You might be selling online Continuous Education Units (CEUs) that are valid
for a period of 2 years. Either it is a 2-year period, or a quarter
(3-month period), there are pricing models that align naturally with business
cycles that fall outside the monthly/yearly dichotomy.

For these cases, it makes sense to define a ``period_length`` which a value
grater than 1.

Example fixtures for a $29 per 2-year plan::

    {
        "fields": {
            "slug": "indie",
            "created_at": "2019-01-01T00:00:00-00:00",
            "title": "Indie",
            "organization": 2,
            "is_active": 1,
            "period_amount": 2900,
            **"period_length": 2,**
            "period_type": 5
        },
        "model": "saas.Plan", "pk": 1
    }


Per-period pricing with discount for advance payments
-----------------------------------------------------

Software-as-a-Service (SaaS) is a relationship business. It makes sense
to incentivize subscribers to pay in advance by offering discounts.

You can specify an ``advance_discount`` on a plan. When you do so, the checkout
workflow will automatically present the option to pay for a multiple periods
in advance to the customer.

Example fixtures for a $29/month and a 20% discount if paid yearly::

    {
        "fields": {
            "slug": "indie",
            "created_at": "2019-01-01T00:00:00-00:00",
            "title": "Indie",
            "organization": 2,
            "is_active": 1,
            "period_amount": 2900,
            "period_type": 4,
            **"advance_discount": 2000**
        },
        "model": "saas.Plan", "pk": 1
    }

Quota pricing
-------------

In some cases, the business model requires to charge base on usage (HTTP
requests, Gigabytes, messages, telephony minutes).
To implement a 3 Part Tariff (3PT) - fixed base, included quota, additional
charges for over quota - we associate a ``UseCharge`` instance to a ``Plan``.

Example fixtures for a $29/month, includes 100 "free" messages,
$0.15 per message afterwards::

    {
        "fields": {
            "slug": "indie",
            "created_at": "2019-01-01T00:00:00-00:00",
            "title": "Indie",
            "organization": 2,
            "is_active": 1,
            "period_amount": 2900,
            "period_type": 4
        },
        "model": "saas.Plan", "pk": 1
    }
    {
        "fields": {
            "slug": "messages",
            "created_at": "2019-01-01T00:00:00-00:00",
            "title": "Per message",
            "plan": 1,
            "use_amount": 15,
            "quota": 100
        },
        "model": "saas.UseCharge", "pk": 1
    }

The functions ``new_use_charge`` and ``record_use_charge`` are the backbone
to implement quota pricing. Each time an ``UseCharge`` event occurs, call
``record_use_charge`` passing a subscription object and a use_charge object.
``record_use_charge`` will take care of recording the event into the transaction
ledger, applying the "free" quota limit as required.
Later on the :doc:`renewals command<periodic-tasks>` will recognize the revenue
for the over-quota usage and generate the appropriate invoices.

Marketplace transaction fee
---------------------------

If you are using a :doc:`Stripe processor backend<backends>`, it is possible
to setup a marketplace with a broker and multiple providers, collecting
a `broker fee <https://stripe.com/docs/connect/direct-charges#collecting-fees>`_
on transaction between subscribers and providers.

To setup a 10% broker fee, update your settings.py as such::

    SAAS = {
        'BROKER': {
            'FEE_PERCENTAGE': 1000,
        }
    }

This will set the ``broker_fee_amount`` field on each ``Plan`` created.
When a ``Charge`` is created for an initial or renewed subscription,
the ``broker_fee_amount`` is applied.


Group buy
---------

The payer is not always the subscriber for a SaaS product. It often happens
in enterprise software, but with an increasingly mobile workforce, it often
the case that a contractor will bring his account while the employer will fit
the bill.
In our previous professional certification e-learning example
(`Per-period pricing with custom periods`_), a clinic pays for its staff
to take the online class, the account and completion certificate belongs
to the nurse (i.e. subscriber). This is implemented through a
&quot;Group buy&quot; feature.

To turn on the &quot;Group buy&quot; feature, set ``is_bulk_buyer`` to ``True``
in an ``Organization`` object::

    {
        "fields": {
            "slug": "xia",
            "created_at": "2019-01-01T00:00:00-00:00",
            "full_name": "Xia Lee",
            "processor": 1,
            "is_active": 1,
            **"is_bulk_buyer": true**
        },
        "model": "saas.Organization", "pk": 3
    }

When a profile with ``is_bulk_buyer == True`` goes through the checkout
workflow, :ref:`steps are added<group_buy>` to allow the user to pay
a subscription on behalf of someone else.
When payment occurs, instead of creating a ``Subscription`` object
for the payer, a one-time ``Coupon`` is mechanically created. The final
subscriber can use that coupon at checkout to zero-out the balance due.
