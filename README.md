djaodjin-saas is a Django application that implements the logic to support
subscription-based Software-as-a-Service businesses.

Major Features:

- Separate billing profiles and authenticated users
- Double entry book keeping ledger
- Flexible security framework

Tested with

- **Python:** 2.7, **Django:** 1.11.20 ([LTS](https://www.djangoproject.com/download/)), **Django Rest Framework:** 3.8.2
- **Python:** 3.6, **Django:** 1.11.20 ([LTS](https://www.djangoproject.com/download/)), **Django Rest Framework:** 3.8.2
- **Python:** 3.6, **Django:** 2.1.8 (latest),       **Django Rest Framework:** 3.8.2

This project contains bare bone templates which are compatible with Django
and Jinja2 template engines. To see djaodjin-saas in action as part
of a full-fledged subscription-based session proxy, take a look
at [djaoapp](https://github.com/djaodjin/djaoapp/).

Full documentation for the project is available at
[Read-the-Docs](http://djaodjin-saas.readthedocs.org/)


Development
===========

After cloning the repository, create a virtualenv environment and install
the prerequisites:

<pre><code>
    $ virtualenv <em>installTop</em>
    $ source <em>installTop</em>/bin/activate
    $ pip install -r testsite/requirements.txt
</code></pre>

To use the testsite, you will need to add the payment processor keys
(see [Processor Backends](http://djaodjin-saas.readthedocs.io/en/latest/backends.html))
and Django secret key into a credentials file. Example with
[Stripe](https://stripe.com/):

<pre><code>
    $ cat ./credentials

    SECRET_KEY = "<em>enough_random_data</em>"
    STRIPE_PUB_KEY = "<em>your_stripe_public_api_key</em>"
    STRIPE_PRIV_KEY = "<em>your_stripe_private_api_key</em>"
</code></pre>

It remains to create the database and populate it with test data.

    $ python ./manage.py migrate --run-syncdb --noinput
    $ python ./manage.py loaddata testsite/fixtures/test_data.json


The test_data.json fixture contains the minimal amount of data to make
the testsite usable. If you want to load a bigger set of dummy data, you
could run the load_test_transactions command.

    $ python ./manage.py load_test_transactions


If all is well then, you are ready to run the server and browse the testsite.

    $ python manage.py runserver

    # Browse http://localhost:8000/
    # Login with username: alice and password: yoyo


Implementation Notes
--------------------

The latest versions of django-restframework (>=3.0) implement paginators
disconnected from parameters in  views (i.e. no more paginate_by). You will
thus need to define ``PAGE_SIZE`` in your settings.py

    $ diff testsite/settings.py
    +REST_FRAMEWORK = {
    +    'PAGE_SIZE': 25,
    +    'DEFAULT_PAGINATION_CLASS':
    +        'rest_framework.pagination.PageNumberPagination',
    +}

This Django App does not send notification e-mails itself. All major
updates that would result in a e-mail sent trigger signals though. It is
straightforward to send e-mails on a signal trigger in the main
Django project. We provide sample e-mail templates here in the
saas/templates/notification/ directory.


Release Notes
=============

0.4.1
  * separates search api for type-ahead candidate lists
  * adds filter and sort to plans API
  * fixes #180

[previous release notes](changelog)

