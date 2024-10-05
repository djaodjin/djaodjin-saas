"""
WSGI config for testsite project.

This module contains the WSGI application used by Django's development server
and any production WSGI deployments. It should expose a module-level variable
named ``application``. Django's ``runserver`` and ``runfcgi`` commands discover
this application via the ``WSGI_APPLICATION`` setting.

Usually you will have the standard Django WSGI application here, but it also
might make sense to replace the whole Django WSGI application with a custom one
that later delegates to the Django one. For example, you could introduce WSGI
middleware here, or combine a Django application with an application of another
framework.

"""
import os, signal

from django.core.wsgi import get_wsgi_application


def save_coverage(*args, **kwargs):
    #pylint:disable=unused-argument
    sys.stderr.write("saving coverage\n")
    cov.stop()
    cov.save()

if os.getenv('DJANGO_COVERAGE'):
    import atexit, sys
    import coverage
    data_file=os.path.join(os.getenv('DJANGO_COVERAGE'),
        ".coverage.%d" % os.getpid())
    cov = coverage.coverage(data_file=data_file)
    sys.stderr.write("start recording coverage in %s\n" % str(data_file))
    cov.set_option("run:relative_files", True)
    cov.start()
    atexit.register(save_coverage)
    try:
        signal.signal(signal.SIGTERM, save_coverage)
    except ValueError as e:
        # trapping signals does not work with manage
        # trying to do so fails with
        # ValueError: signal only works in main thread
        pass

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testsite.settings")

# This application object is used by any WSGI server configured to use this
# file. This includes Django's development server, if the WSGI_APPLICATION
# setting points here.
#pylint: disable=invalid-name
application = get_wsgi_application()
