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
    $ pip install -r requirements.txt -r testsite/requirements.txt
    $ python manage.py syncdb
    $ python manage.py loaddata testsite/fixtures/test_data.json
    $ python manage.py runserver

    # Browse http://localhost:8000/
    # Login with username: donny and password: yoyo
