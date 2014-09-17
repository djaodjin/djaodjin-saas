Flexible Security Framework
===========================

Business logic sometimes dictates that a provider has minimal access the billing
profile of a customer and sometimes a provider must be able to update the credit
card associated to a customer through a phone call.

In order to support multiple usage patterns and security constraints,
authorization is not embeded into the djaodjin-saas logic but rather
implemented as URL decorators. It is the responsability of the developper
to associate decorators to URLs as dictated by the business requirements.

The security framework defines two roles for the ``User`` / ``Organization``
relationship: *Manager* and *Contributor*.

Typically *Manager* have full access to an Organization while *Contributor*
are restricted to read-only permissions.

Decorators Available
--------------------

.. automodule:: saas.decorators
   :members: requires_agreement, requires_paid_subscription, requires_direct,
    requires_provider, requires_self_provider


.. rubric:: Design Note

We used to decorate the saas views with the "appropriate" decorators,
except in many projects appropriate had a different meaning. It turns out
that the access control logic is better left to be configured
in the site URLConf through extensions like `django-urldecorators`_.
This is not only more flexible but also make security audits a lot easier.

.. _django-urldecorators: https://github.com/mila/django-urldecorators
