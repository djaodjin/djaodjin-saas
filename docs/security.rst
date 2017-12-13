Flexible Role-based Access Control
==================================

Business logic sometimes dictates that a provider has minimal access the billing
profile of a customer and sometimes a provider must be able to update the credit
card associated to a customer while on a phone call with that customer.

In order to support multiple usage patterns and security constraints,
authorization is not embeded into the djaodjin-saas logic but rather
implemented as URL decorators. It is the responsability of the developper
to associate decorators to URLs as dictated by the business requirements.

The security framework defines a generic ``RoleDescription`` whose purpose
is to define a role a ``User`` has on an ``Organization`` (see
:doc:`grant and request roles <relations>`).

A organization-agnostic manager role always exists and helps with bootstrapping
the security policies. In most setups a second role, for example, a contributor
role is implemented.
Typically *manager* have full access to an Organization while *contributor*
are restricted to read-only permissions.

Examples
--------

Let's say you want to give POST access to contributors on
:doc:`/api/billing/charges/:charge/refund/<api>`,
you would write the following in your urls.py:

.. code-block:: python

    from urldecorators import url
    from saas.api.charges import ChargeRefundAPIView

    urlpatterns = [

        url(r'^billing/charges/(?P<charge>[a-zA-Z0-9_\-\+\.]+)/refund/',
            ChargeRefundAPIView.as_view(),
            name='saas_api_charge_refund',
            decorators=['saas.decorators.requires_provider_weak']),
    ]

The previous example uses `django-urldecorators`_ and a
``saas.decorators.requires_provider_weak decorator``.

The ``saas.urls`` module has been split in "common" set of functionalities
such that in many cases you can decorate each include() with an appropriate
decorator instead of each URL one by one. (ex: `testsite/urls.py`_)

A blog post on `Django Rest Framework, AngularJS and permissions`_
might also be a useful read.


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

.. _testsite/urls.py: https://github.com/djaodjin/djaodjin-saas/blob/master/testsite/urls.py

.. _Django Rest Framework, AngularJS and permissions: http://djaodjin.com/blog/drf-angularjs-access-control.blog.html
