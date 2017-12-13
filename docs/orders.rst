Placing on Order
================

A ``Subscription`` is created when a ``Plan`` is selected and paid for.
As simple as it sounds, there are many variants to implement the previous
sentence.

Basic Pipeline
^^^^^^^^^^^^^^
In the most basic pipeline, a user becomes a subscriber in 2 steps:

1. Click a ``Plan`` on the /pricing/ page
2. Submit credit card information

Pipeline with Multiple Periods Paid in Advance
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
It is always better to receive more cash up-front so an intermediate step
is often introduced to enable to pre-pay multiple periods in advance at
a discount.

1. Click a ``Plan`` on the /pricing/ page
2. Pick the number of periods paid in advance
3. Submit credit card information

Pipeline with Multiple Products in Shopping Cart
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A growing business often offers multiple products (i.e. ``Plan``) that are
cross-saled to new and existing customers. In that case, the /pricing/ page
is replaced by a more complex catalog. Cart and checkout concepts appear.

1. Add multiple ``Plan`` to a user cart
2. Click a checkout button
3. Submit credit card information

.. _group_buy:

Pipeline to Bulk Subscribe Third-parties
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Software-as-a-Service that target businesses (B2B) and/or other kind
of structured groups almost always require one entity to pay for subscriptions
on behalf of users that belong to it. This can be implemented through
managers (or custom roles) to the subscribed entity
(see :doc:`Security <security>`) or through the entity buying multiple
subscriptions in bluk, on behalf of its users. The later case requires
an extra step to subscribe those third parties.

1. Click a ``Plan`` on the /pricing/ page
2. Enter email address of users to subscribe
3. Submit credit card information

Full Pipeline
^^^^^^^^^^^^^

Of course, all of the above cases can be combined together, which leads
to a full pipeline as such:

.. image:: order-pipeline.*

1. Add multiple ``Plan`` to a user cart
2. Click a checkout button
3. Pick the number of periods paid in advance
4. Enter email address of users to subscribe
5. Submit credit card information


Django Views
------------

.. automodule:: saas.views.billing

.. image:: order-views.*

.. autoclass:: saas.views.billing.CartBaseView

.. autoclass:: saas.views.billing.BalanceView

.. autoclass:: saas.views.billing.CartView


