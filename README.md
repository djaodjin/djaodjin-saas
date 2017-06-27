djaodjin-saas is a Django application that implements the logic to support
subscription-based Sofware-as-a-Service businesses.

Major Features:

- Separate billing profiles and authenticated users
- Double entry book keeping ledger
- Flexible security framework

Full documentation for the project is available at [Read-the-Docs](http://djaodjin-saas.readthedocs.org/)

Development
===========

After cloning the repository, create a virtualenv environment and install
the prerequisites:

    $ virtualenv-2.7 _installTop_
    $ source _installTop_/bin/activate
    $ pip install -r testsite/requirements.txt


To use the testsite, you will need to add the payment processor keys
(see [Processor Backends](http://djaodjin-saas.readthedocs.io/en/latest/backends.html))
and Django secret key into a credentials file. Example with
[Stripe](https://stripe.com/):

    $ cat ./credentials

    SECRET_KEY = "_enough_random_data_"
    STRIPE_PUB_KEY = "_your_stripe_public_api_key_"
    STRIPE_PRIV_KEY = "_your_stripe_private_api_key_"


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
    # Login with username: donny and password: yoyo


Implementation Notes
--------------------

The latest versions of django-restframework (>=3.0) implement paginators
disconnected from parameters in  views (i.e. no more paginate_by). You will
thus need to define ``PAGE_SIZE`` in your settings.py

    $ diff testsite/settings.py
    +REST_FRAMEWORK = {
    +    'PAGE_SIZE': 25,
    +}

This Django App does not send notification e-mails itself. All major
updates that would result in a e-mail sent trigger signals though. It is
straightforward to send e-mails on a signal trigger in the main
Django project. We provide sample e-mail templates here in the
saas/templates/notification/ directory.


Release Notes
=============

0.2.6

  * Compatible with Python 3.6

[previous release notes](changelog)

