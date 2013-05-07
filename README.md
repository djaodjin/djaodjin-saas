This code was taken out of fortylines main repo and generalized into
an opensource Django SaaS framework.

Development
===========

After cloning the repository, create a virtualenv environment, install
the prerequisites, create and load initial data into the database, then
run the testsite webapp.

    $ virtualenv-2.7 _installTop_
    $ source _installTop_/bin/activate
    $ pip install -r requirements.txt
    $ python manage.py syncdb
    $ python manage.py loaddata testsite/fixtures/initial_data.json
    $ python manage.py runserver

    # Browse http://localhost:8000/saas/root
    # Login with username: demo and password: yoyo
