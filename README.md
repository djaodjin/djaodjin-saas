djaodjin-saas is a Django application that implements the logic to support
subscription-based Sofware-as-a-Service businesses.

Major Features:

- Separate billing profiles and authenticated users
- Double entry book keeping ledger
- Flexible security framework

Full documentation for the project is available at [Read-the-Docs](http://djaodjin-saas.readthedocs.org/)

Development
===========

After cloning the repository, create a virtualenv environment, install
the prerequisites, create and load initial data into the database, then
run the testsite webapp.

    $ virtualenv-2.7 _installTop_
    $ source _installTop_/bin/activate
    $ pip install -r testsite/requirements.txt
    $ make initdb
    $ python manage.py runserver

    # Browse http://localhost:8000/
    # Login with username: donny and password: yoyo

To test payment through [Stripe](https://stripe.com/):

1. Add your Stripe keys in the credentials file.

    STRIPE_PUB_KEY = "_your_stripe_public_api_key_"

    STRIPE_PRIV_KEY = "_your_stripe_private_api_key_"

2. This Django App does not send notification e-mails itself. All major
updates that would result in a e-mail sent trigger signals though. It is
straightforward to send e-mails on a signal trigger in the main
Django project. We provide sample e-mail templates here in the
saas/templates/notification/ directory.

The latest versions of django-restframework implement paginators disconnected
from parameters in  views (i.e. no more paginate_by). You will thus need
to define ``PAGE_SIZE`` in your settings.py

    $ diff testsite/settings.py
    +REST_FRAMEWORK = {
    +    'PAGE_SIZE': 25,
    +}


Release Notes
=============

0.2.1

  * Create dashboard views
  * Generate requests for a role on an organization
  * Add Razorpay backend

[previous release notes](changelog)

