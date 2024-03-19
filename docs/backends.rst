Processor Backends
==================

There always needs to be a special ``Organization``, the processor in your
database. The processor represents the payment processor backend in charge
and deposit transactions.

``Organization`` with pk=1 will be considered to be the default processor.
This can be overridden by defining ``PROCESSOR_ID`` in the settings block.

.. code-block::

    $ cat settings.py

    SAAS = {
        'PROCESSOR_ID': 1
    }

Flutterwave configuration
-------------------------

.. automodule:: saas.backends.flutterwave_processor


Razorpay configuration
----------------------

.. automodule:: saas.backends.razorpay_processor

Stripe configuration
--------------------

.. automodule:: saas.backends.stripe_processor.base


Writing a new processor backend
-------------------------------

To get started, you can look at the
`saas.backends.fake_processor.FakeProcessorBackend` which is a mockup of
the methods a payment processor backend is expected to implement. As seen
on the diagram below, the first two methods that are important to implement
are `get_payment_context` and `create_payment`.

Most modern payment processors return a processor token to the browser client
when passed credit card information (card number, ccv, street address, etc.)
that you post to your backend (running djaodjin-saas) to effect the charge.

.. image:: checkout-http-timing.*

`get_payment_context` returns the information that the browser client will
need to pass to the payment processor to authenticate your application, while
`create_payment` will effect the payment when payments are handled in a two
steps process. You will need to refer to the specific payment processor
documentation to decide what goes into `get_payment_context` and what goes
into `create_payment` (See
`saas.backends.stripe_processor.base.StripeBackend.get_payment_context`_ and
`saas.backends.stripe_processor.base.StripeBackend.create_payment`_
for examples).

How to debug "__name__ is not associated to an account on the processor and no token was passed."
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There are two ways a charge is created through
`saas.AbstractOrganization.checkout`:

1. A processor token representing the credit card is passed to the method
2. The organization/profile has a credit card on file
   (`processor_card_key is not None`).

The error is raised when neither of the conditions above are true.

Unless you collect credit card information before hand to charge at a later
date, the most likely case is that you will pass a processor token the first
time a billing profile is charged through a checkout page.

First is to check the processor token is passed properly to the backend
by using your favorite debugger to look at
`CheckoutFormMixin.form_valid.processor_token`_,
or `CheckoutAPIView.post.token`_ if you use the checkout page or checkout API
respectively. You can also look through the DevTools in your browser to
find out what payload is passed to the POST request. It is highly likely
there are no processor token passed, or the processor token is passed under
a different name that the expected one.

Assuming you have written the Javascript interacting with the payment processor
to retrieve a one-time token (see `djaodjin-stripe.js`_ for example), you would
most likely receive an browser error if `get_payment_context` did not pass
the correct public key and other expected identifiers to pass to the processor
to create a payment token.



.. _saas.backends.stripe_processor.base.StripeBackend.get_payment_context: https://github.com/djaodjin/djaodjin-saas/blob/d19d11d9e473aa66c57fba675261254f51b977ba/saas/backends/stripe_processor/base.py#L784
.. _saas.backends.stripe_processor.base.StripeBackend.create_payment: https://github.com/djaodjin/djaodjin-saas/blob/d19d11d9e473aa66c57fba675261254f51b977ba/saas/backends/stripe_processor/base.py#L398
.. _CheckoutFormMixin.form_valid.processor_token: https://github.com/djaodjin/djaodjin-saas/blob/d19d11d9e473aa66c57fba675261254f51b977ba/saas/views/billing.py#L263
.. _CheckoutAPIView.post.token: https://github.com/djaodjin/djaodjin-saas/blob/d19d11d9e473aa66c57fba675261254f51b977ba/saas/api/billing.py#L571
.. _djaodjin-stripe.js: https://github.com/djaodjin/djaodjin-saas/blob/d19d11d9e473aa66c57fba675261254f51b977ba/saas/static/js/djaodjin-stripe.js#L311
