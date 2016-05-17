# Django settings for testsite project.

import os.path, sys

from django.core.urlresolvers import reverse_lazy
from django.contrib.messages import constants as messages


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_config(confpath):
    '''
    Given a path to a file, parse its lines in ini-like format, and then
    set them in the current namespace.
    '''
    # todo: consider using something like ConfigObj for this:
    # http://www.voidspace.org.uk/python/configobj.html
    import re
    if os.path.isfile(confpath):
        sys.stderr.write('config loaded from %s\n' % confpath)
        with open(confpath) as conffile:
            line = conffile.readline()
            while line != '':
                if not line.startswith('#'):
                    look = re.match(r'(\w+)\s*=\s*(.*)', line)
                    if look:
                        value = look.group(2) \
                            % {'LOCALSTATEDIR': BASE_DIR + '/var'}
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

load_config(os.path.join(BASE_DIR, 'credentials'))

if not hasattr(sys.modules[__name__], "SECRET_KEY"):
    from random import choice
    SECRET_KEY = "".join([choice(
        "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^*-_=+") for i in range(50)])

DEBUG = True
FEATURES_DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(os.getcwd(), 'db.sqlite'),
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}

REST_FRAMEWORK = {
    'PAGE_SIZE': 25,
}

MESSAGE_TAGS = {
    messages.ERROR: 'danger'
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'America/Chicago'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

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

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware'
)

ROOT_URLCONF = 'testsite.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'testsite.wsgi.application'

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
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

LOGIN_URL = reverse_lazy('login')
LOGIN_REDIRECT_URL = reverse_lazy('app')

# Allow user to enter month in durationfield
DURATIONFIELD_ALLOW_MONTHS = True

# Configuration of djaodjin-saas
SAAS = {
  'PLATFORM': 'cowork',
  'PROCESSOR': {
      'BACKEND': 'saas.backends.stripe_processor.StripeBackend',
      'PRIV_KEY': getattr(sys.modules[__name__], "STRIPE_PRIV_KEY", None),
      'PUB_KEY': getattr(sys.modules[__name__], "STRIPE_PUB_KEY", None),
#      'BACKEND': 'saas.backends.razorpay_processor.RazorpayBackend',
#      'PRIV_KEY': getattr(sys.modules[__name__], "RAZORPAY_PRIV_KEY", None),
#      'PUB_KEY': getattr(sys.modules[__name__], "RAZORPAY_PUB_KEY", None),
    }
}

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

# Templates (Django 1.8+)
# ----------------------
TEMPLATE_REVERT_TO_DJANGO = True

if TEMPLATE_REVERT_TO_DJANGO:
    sys.stderr.write("Use Django templates engine.\n")
    TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'OPTIONS': {
            'context_processors': [
    'django.contrib.auth.context_processors.auth', # because of admin/
    'django.template.context_processors.request',
    'django.template.context_processors.media',
            ],
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader'],
            'libraries': {},
            'builtins': [
                'saas.templatetags.saas_tags',
                'testsite.templatetags.testsite_tags']
        }
    }
    ]
else:
    sys.stderr.write("Use Jinja2 templates engine.\n")
    TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.jinja2.Jinja2',
        'DIRS': (os.path.join(BASE_DIR, 'testsite', 'templates', 'jinja2'),
                 os.path.join(BASE_DIR, 'testsite', 'templates'),
                 os.path.join(BASE_DIR, 'saas', 'templates')),
        'OPTIONS': {
            'environment': 'testsite.jinja2.environment'
        }
    }]
