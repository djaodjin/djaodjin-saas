# Django settings for testsite project.

import os.path

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_config(confpath):
    '''
    Given a path to a file, parse its lines in ini-like format, and then
    set them in the current namespace.
    '''
    # todo: consider using something like ConfigObj for this:
    # http://www.voidspace.org.uk/python/configobj.html
    import re, sys
    if os.path.isfile(confpath):
        sys.stderr.write('config loaded from %s\n' % confpath)
        with open(confpath) as conffile:
            line = conffile.readline()
            while line != '':
                if not line.startswith('#'):
                    look = re.match(r'(\w+)\s*=\s*(.*)', line)
                    if look:
                        value = look.group(2) \
                            % {'LOCALSTATEDIR': APP_ROOT + '/var'}
                        try:
                            # Once Django 1.5 introduced ALLOWED_HOSTS (a tuple
                            # definitely in the site.conf set), we had no choice
                            # other than using eval. The {} are here to restrict
                            # the globals and locals context eval has access to.
                            # pylint: disable=eval-used
                            setattr(sys.modules[__name__],
                                    look.group(1).upper(), eval(value, {}, {}))
                        except StandardError:
                            raise
                line = conffile.readline()
    else:
        sys.stderr.write('warning: config file %s does not exist.\n' % confpath)

load_config(os.path.join(APP_ROOT, 'credentials'))

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(os.getcwd(), 'saas_testsite.sqlite'),
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'America/Chicago'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 2

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = ''

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'q%cn)2_5&amp;jkbxxi!qo0o@7i^j-zpk0oje(++#0se@5c38p4e-7'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
)

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'testsite.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'testsite.wsgi.application'

TEMPLATE_DIRS = ()

# django-app-metrics (not installing celery)
CELERY_ALWAYS_EAGER = True

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Uncomment the next line to enable the admin:
    'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
    'rest_framework',
    'django_countries',
    'saas',
    'testsite'
)

# Allow user to enter month in durationfield
DURATIONFIELD_ALLOW_MONTHS = True

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'logfile':{
            'level':'DEBUG',
            'class':'logging.StreamHandler',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'saas': {
            'handlers': ['logfile'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
#        'django.db.backends': {
#             'handlers': ['logfile'],
#             'level': 'DEBUG',
#             'propagate': True,
#        },
    }
}
