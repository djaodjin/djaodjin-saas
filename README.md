djaodjin-saas is a Django application that implements the logic to support
subscription-based Software-as-a-Service businesses.

Major Features:

- Separate billing profiles and authenticated users
- Double entry book keeping ledger
- Flexible security framework

Tested with

- **Python:** 2.7, **Django:** 1.11 ([LTS](https://www.djangoproject.com/download/)), **Django Rest Framework:** 3.9.4
- **Python:** 3.6, **Django:** 1.11 ([LTS](https://www.djangoproject.com/download/)), **Django Rest Framework:** 3.9.4
- **Python:** 3.6, **Django:** 2.2 (latest, [LTS](https://www.djangoproject.com/download/)), **Django Rest Framework:** 3.9.4

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
    $ python -m venv .venv
    $ source .venv/bin/activate
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

It remains to create and [populate the database with required objects](https://djaodjin-saas.readthedocs.io/en/latest/getting-started.html#setting-up-a-software-as-a-service-site).

    $ python ./manage.py migrate --run-syncdb --noinput
    $ python ./manage.py loaddata testsite/fixtures/initial_data.json
    $ python ./manage.py createsuperuser

You can further generate a set of dummy data data to populate the site.

    $ python ./manage.py load_test_transactions

Side note: If create your own fixtures file (ex: testsite/fixtures/test_data.json)
and attempt to load them with a Django version *before* 2 while the Python
executable was linked with a SQLite version *after* 3.25, you might stumble upon
the well-known [SQLite 3.26 breaks database migration ForeignKey constraint, leaving <table_name>__old in db schema](http://djaodjin.com/blog/django-2-2-with-sqlite-3-on-centos-7.blog.html#sqlite-django-compatibility) bug.
Your best bet is to use Django2+ or delete the migrations/ directory.

If all is well then, you are ready to run the server and browse the testsite.

    $ python manage.py runserver

    # Browse http://localhost:8000/


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

0.8.3

  * adds implicit role to user when none exists
  * uses class name instead of HTML node indexes as hooks in checkout pages
  * uses consistent balance_amount/balance_unit accross APIs
  * replaces django-urldecorators by djaodjin-rules in testsite

[previous release notes](changelog)
