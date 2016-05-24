Processor Backends
==================

There always needs to be a special ``Organization``, the processor in your
database. The processor represents the payment processor backend in charge
and deposit transactions.

``Organization`` with pk=1 will be considered to be the default processor.
This can be overridden by defining ``PROCESSOR_ID`` in the settings block.

.. code-block:: python

    $ cat settings.py

    SAAS = {
        'PROCESSOR_ID': 1
    }


Razorpay configuration
----------------------

.. automodule:: saas.backends.razorpay_processor

Stripe configuration
--------------------

.. automodule:: saas.backends.stripe_processor.base
