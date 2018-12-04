The Subscription Cycle
======================

The ``Subscription`` model (see :doc:`models <models>`) is the corner stone
on which access to the service is authorized. It is also a fundamental block
of the :doc:`Flexible Security Framework <security>`.

.. autoclass:: saas.models.Subscription

The djaodjin-saas logic supports subscribe and unsubscribe to multiple plans
at any one time but, by default, will generate credit card charges on a billing
cycle. At the time a customer first subscribes to a ``Plan``, a billing cycle is
established for the ``Organization``. From that time on, a customer is billed
at the begining of each billing cycle for all services subscribed to.

.. image:: timeline.*

Thus all subscriptions are charged as a single credit card charge through
the payment processor (see :doc:`backends available <backends>`).

In normal business operations, service is available as soon as customer
subscribes; service becomes unavailable at the end of a billing cycle.

Whenever potential fraud is detected, that is a customer's card is denied
N number of times or a chargeback is created, a customer is locked out
immediately.


Renewals
--------

Plans can be configured to create one-time-only subcriptions, repeat
subscriptions or auto-renewal subscriptions.

+-----------------+--------------------------------------+--------------------+
|Plan.renewal_type|Description                           | Example            |
+=================+======================================+====================+
|ONE_TIME         | The provider wishes to upgrade       | A 30-day trial plan|
|                 | subscriber to a different plan       |                    |
|                 | when the period ends.                |                    |
+-----------------+--------------------------------------+--------------------+
|REPEAT           | The service is provided on request.  | Car rental with    |
|                 | It requires the customer to          | pre-negotiatied    |
|                 | explicitely take action in           | rates              |
|                 | the product.                         |                    |
+-----------------+--------------------------------------+--------------------+
|AUTO_RENEW       | The service is provided continuoulsly| web hosting        |
|                 | until canceled.                      |                    |
+-----------------+--------------------------------------+--------------------+

When a ``Subscription`` for a ``Plan`` where ``renewal_type == AUTO_RENEW``
is created, ``Subscription.auto_renew`` is set to ``True`` to tell
the :doc:`periodic renewal task <periodic-tasks>` to automatically extends
the subscription for one more period in the day before it ends.

The function ``saas.renewals.extend_subscriptions(at_time)`` iterates through
all active subscription that ends in a day of ``at_time`` and which have
``auto_renew == True``, and records a subscription order in the ``Transaction``
:doc:`ledger<ledger>` for each of them.

Later, ``saas.renewals.create_charges_for_balance`` calls
the :doc:`processor backend <backends>` to create an actual charge
for the balance due by an ``Organization``.

When a subscription is canceled, ``auto_renew`` is set to ``False``. ``ends_at``
is set to the current date/time (cancel now) or left unchanged (cancel at end
of period).


Expiration notices
------------------

Expiration notices (if any) are triggered 90, 60, 30, 15 and 1 day(s) before
a subscription ends. This can be changed through the EXPIRE_NOTICE_DAYS
in settings.py:

    .. code-block:: python

        SAAS = {
            "EXPIRE_NOTICE_DAYS": [90, 60, 30, 15, 1]
        }

Different types of expiration notices are sent based on the value
of ``Plan.renewal_type``, ``Subscription.auto_renew``, and the subscriber
payment method.

A subscriber payment method (i.e. ``Organization``) can be either be absent,
valid or expired. The payment method status is determined at the time
a renewal ``Charge`` would be created.

There would be 18 (3 * 2 * 3) combinations of expiration notices if a
few combinations could not happen.

- ``Subscription.auto_renew`` shall be false when ``Plan.renewal_type`` is
``ONE_TIME`` because it does not make sense to have a subscription that
renews if the plan states the subscription length is fixed to one period.

- ``Subscription.auto_renew`` shall also be set to false when
  ``Plan.renewal_type`` is ``REPEAT``. Without adding this constraint,
  there is no direct means to detect subscriptions to a repeat plan that would
  be "canceled".

We assume here that cancelation of repeat plans is uninteresting (if either
possible) and state that cancelation only makes sense with plans having
an auto-renew behavior. Thus, instead of adding another state variable, we use
``Plan.renewal == AUTO_RENEW && Subscription.auto_renew == false``
to detect cancelations of auto-renewals.


The signals triggered by ``saas.renewals.trigger_expiration_notices``
are such for the available combinations

+----------+----------------+----------------+---------------------------------+
| Plan     | Subscription   | Organization   | ACTION                          |
|          |                | payment method |                                 |
+==========+================+================+=================================+
|ONE_TIME  |auto_renew=false|ABSENT          | Upgrades notice                 |
+----------+----------------+----------------+---------------------------------+
|ONE_TIME  |auto_renew=false|VALID           | Upgrades notice                 |
+----------+----------------+----------------+---------------------------------+
|ONE_TIME  |auto_renew=false|EXPIRED         | Upgrades notice                 |
+----------+----------------+----------------+---------------------------------+
|REPEAT    |auto_renew=false|ABSENT          | Expiration notice               |
+----------+----------------+----------------+---------------------------------+
|REPEAT    |auto_renew=false|VALID           | Expiration notice               |
+----------+----------------+----------------+---------------------------------+
|REPEAT    |auto_renew=false|EXPIRED         | Expiration notice               |
+----------+----------------+----------------+---------------------------------+
|AUTO_RENEW|auto_renew=false|ABSENT          | None (canceled)                 |
+----------+----------------+----------------+---------------------------------+
|AUTO_RENEW|auto_renew=false|VALID           | None (canceled)                 |
+----------+----------------+----------------+---------------------------------+
|AUTO_RENEW|auto_renew=false|EXPIRED         | None (canceled)                 |
+----------+----------------+----------------+---------------------------------+
|AUTO_RENEW|auto_renew=true |ABSENT          | Attach payment method notice    |
+----------+----------------+----------------+---------------------------------+
|AUTO_RENEW|auto_renew=true |VALID           | None                            |
+----------+----------------+----------------+---------------------------------+
|AUTO_RENEW|auto_renew=true |EXPIRED         |Payment method will expire notice|
+----------+----------------+----------------+---------------------------------+

