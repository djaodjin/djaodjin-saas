This is the Django framework on which DjaoDjin SaaS backend is built.


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
