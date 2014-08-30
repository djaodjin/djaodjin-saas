Subscriptions
=============

.. autoclass:: saas.models.Subscription

The djaodjin-saas logic supports subscribe and unsubscribe to multiple plans
at any one time but, by default, will generate credit card charges on a billing
cycle. At the time a customer first subscribes to a ``Plan``, a billing cycle is
established for the ``Organization``. From that time on, a customer is billed
at the begining of each billing cycle for all services subscribed to.

.. image:: timeline.*

Thus all subscriptions are charged as a single credit card charge through
the payment processor (by default Stripe).

In normal business operations, service is available as soon as customer
subscribes; service becomes unavailable at the end of a billing cycle.

Whenever potential fraud is detected, that is a customer's card is denied
N number of times or a chargeback is created, a customer is locked out
immediately.


