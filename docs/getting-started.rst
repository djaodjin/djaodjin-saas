Getting Started
===============

`djaodjin-saas`_ is a Django app
that implements the logic to support subscription-based Software-as-a-Service
businesses.

As such you will need to be familiar with Django Apps and Django Projects (see
`Getting started with Django`_).

If you are looking to see the features djaodjin-saas brings to your Django
project without going through the setup inside your own Django project, run
the testsite committed alongside the application code (see steps in
`README.md`_).

If you are interested in what a fully-integrated SaaS Django project could look
like, browse the `djaoapp`_ code
repository and/or the `djaoapp livedemo`_
(**Warning:** the livedemo is for the djaoapp, fully-integrated SaaS Django
project. There is quite some work to integrate an auth app, a rule-based
access control app as well as HTML/CSS required to make all of it acceptable
to modern UI standards).


Installation and configuration
------------------------------

We assume here you already created a
`Python virtual environment<https://docs.python.org/3/library/venv.html>`,
installed Django and created a Django project which will be using
the `djaodjin-saas`_ Django App.

First download and install the latest version of djaodjin-saas into your
Python virtual environment.

.. code-block:: shell

    $ pip install djaodjin-saas


Edit your project urls.py to add the djaojdin-saas urls

.. code-block:: python

   urlpatterns += [
       path('', include('saas.urls')),
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

Following is a fixtures file doing just that (ref:
`How to load fixtures in a Django project`_)

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
        "period_type": 4,
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
        "period_type": 4,
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
        "period_type": 4,
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
The :doc:`checkout pipeline<orders>` support orders for multiple plans
in one payment. All you have to do is thus:

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


.. _djaodjin-saas: https://github.com/djaodjin-saas/
.. _Getting started with Django: https://docs.djangoproject.com/en/4.2/intro/
.. _README.md: https://github.com/djaodjin/djaodjin-saas/blob/master/README.md
.. _djaoapp: https://github.com/djaodjin/djaoapp/
.. _djaoapp livedemo: https://livedemo.djaoapp.com/
.. _How to load fixtures in a Django project: https://docs.djangoproject.com/en/4.2/topics/db/fixtures/
