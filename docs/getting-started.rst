Getting Started
===============

Installation and configuration
------------------------------

First download and install the latest version of djaodjin-saas into your
Python virtual environment.

.. code-block:: shell

    $ pip install djaodjin-saas


Edit your project urls.py to add the djaojdin-saas urls

.. code-block:: python

   urlpatterns += [
       url(r'^', include('saas.urls')),
   ]


Edit your project settings.py to add saas into the ``INSTALLED_APPS``
and a SAAS configuration block

.. code-block:: python

    INSTALLED_APPS = (
        ...
        'saas'
    )

    SAAS = {
        'PROCESSOR': {
            'BACKEND': 'saas.backends.stripe_processor.StripeBackend',
            'PRIV_KEY': "_Your_Stripe_Private_Key_",
            'PUB_KEY': "_Your_Stripe_Public_Key_",
        }
    }

Various :doc:`payment processor backends<backends>` are available.

The latest versions of django-restframework implement paginators disconnected
from parameters in  views (i.e. no more paginate_by). You will thus need
to define ``PAGE_SIZE`` in your settings.py

.. code-block:: python

    REST_FRAMEWORK = {
        'PAGE_SIZE': 25,
        'DEFAULT_PAGINATION_CLASS':
            'rest_framework.pagination.PageNumberPagination',
    }

There is no access policies by default on the djaodjin-saas URLs. It is thus
your responsability to add the appropriate decorators to restrict which users
can access which URL. A set of common decorators in Software-as-a-Service
setups is provided as part of the :doc:`Flexible Security Framework <security>`.


Setting up a Software-as-a-Service site
---------------------------------------

To setup a site with three plans (basic, premium and ultimate), we will create
an ``Organization`` for the payment processor and an ``Organization`` for the
provider / broker together with three ``Plan`` that belong to the provider
(see :doc:`database schema <models>`). We will also need to create an default
``Agreement`` for the terms of use of the site.

**Example fixtures**:

.. code-block:: json

    [{
        "fields": {
          "slug": "stripe",
          "full_name": "Stripe",
          "created_at": "2016-01-01T00:00:00-09:00",
          "processor": 1,
          "is_active": 1
        },
        "model": "saas.Organization", "pk": 1
    },
    {
        "fields": {
          "slug": "terms-of-use",
          "title": "Terms Of Use",
          "modified": "2016-01-01T00:00:00-09:00"
        },
        "model": "saas.agreement", "pk": 1
    },
    {
        "fields": {
          "slug": "cowork",
          "full_name": "ABC Corp.",
          "created_at": "2016-01-01T00:00:00-09:00",
          "email": "support@localhost.localdomain",
          "phone": "555-555-5555",
          "street_address": "1 ABC loop",
          "locality":  "San Francisco",
          "region": "CA",
          "postal_code": "94102",
          "country": "US",
          "processor": 1,
          "is_provider": 1,
          "is_active": 1
        },
        "model": "saas.Organization", "pk": 2
    },
    {
      "fields": {
        "slug": "basic",
        "title": "Basic",
        "created_at": "2016-01-01T00:00:00-09:00",
        "setup_amount": 0,
        "period_amount": 2000,
        "interval": 4,
        "description": "Basic Plan",
        "organization" : 2,
        "is_active": 1
      },
      "model" : "saas.Plan", "pk": 1
    },
    {
      "fields": {
        "slug": "premium",
        "title": "Premium",
        "created_at":"2016-01-01T00:00:00-09:00",
        "setup_amount": 0,
        "period_amount": 6900,
        "interval": 4,
        "description": "Premium Plan",
        "organization" : 2,
        "is_active": 1
      },
      "model" : "saas.Plan", "pk": 2
    },
    {
      "fields": {
        "slug": "ultimate",
        "title": "Ultimate",
        "created_at": "2016-01-01T00:00:00-09:00",
        "setup_amount": 0,
        "period_amount": 8900,
        "interval": 4,
        "description": "Ultimate Plan",
        "organization" : 2,
        "is_active": 1
      },
      "model" : "saas.Plan", "pk": 3
    }]

To setup different pricing models such as a 3 Part Tariff (3PT),
read about the :doc:`supported pricing models<pricing>`.


Selling add-ons plans
---------------------

Subscribers can be subscribed to any number of ``Plan``.
The :doc:`cart API<_api_cart>` and :doc:`checkout pipeline<orders>` support
orders for multiple plans in one payment. All you have to do is thus:

1. Create a new ``Plan``
2. Modify the pricing page from a one-click to a shopping cart experience


Restricting features based on a plan
------------------------------------

In decorators.py there is a ``requires_paid_subscription`` decorator which
is part of the :doc:`Flexible Security Framework <security>`.

What you would do to allow/deny access to certain features (i.e. URLs) based
on the subscribed-to Plan is to decorate the view implementing the feature.

**Example**:

.. code-block:: python

   urls.py:

   from saas.decorators import requires_paid_subscription
   from .views import FeatureView

   urlpatterns = [
   \.\.\.
       url(r'^(?P<organization>[a-z])/(?P<subscribed_plan>[a-z])/feature/',
           requires_paid_subscription(FeatureView.as_view()), name='feature'),
    \.\.\.
   ]
