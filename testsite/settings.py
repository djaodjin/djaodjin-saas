# Django settings for testsite project.

import logging, os.path, re, sys

from django.contrib.messages import constants as messages
from saas.compat import reverse_lazy


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_DIR = os.getenv('RUN_DIR', os.getcwd())
DB_NAME = os.path.join(RUN_DIR, 'db.sqlite')
LOG_FILE = os.path.join(RUN_DIR, 'testsite-app.log')

DEBUG = True
FEATURES_DEBUG = True
TEMPLATE_REVERT_TO_DJANGO = True
JS_FRAMEWORK = 'vuejs'
SAAS_ORGANIZATION_MODEL = 'saas.Organization'

ALLOWED_HOSTS = ('*',)

def load_config(confpath):
    '''
    Given a path to a file, parse its lines in ini-like format, and then
    set them in the current namespace.
    '''
    # todo: consider using something like ConfigObj for this:
    # http://www.voidspace.org.uk/python/configobj.html
    if os.path.isfile(confpath):
        sys.stderr.write('config loaded from %s\n' % confpath)
        with open(confpath) as conffile:
            line = conffile.readline()
            while line != '':
                if not line.startswith('#'):
                    look = re.match(r'(\w+)\s*=\s*(.*)', line)
                    if look:
                        value = look.group(2) \
                            % {'LOCALSTATEDIR': RUN_DIR + '/var'}
                        try:
                            # Once Django 1.5 introduced ALLOWED_HOSTS (a tuple
                            # definitely in the site.conf set), we had no choice
                            # other than using eval. The {} are here to restrict
                            # the globals and locals context eval has access to.
                            # pylint: disable=eval-used
                            setattr(sys.modules[__name__],
                                    look.group(1).upper(), eval(value, {}, {}))
                        except Exception:
                            raise
                line = conffile.readline()
    else:
        sys.stderr.write('warning: config file %s does not exist.\n' % confpath)

load_config(os.path.join(
    os.getenv('TESTSITE_SETTINGS_LOCATION', RUN_DIR), 'credentials'))

if not hasattr(sys.modules[__name__], "SECRET_KEY"):
    from random import choice
    SECRET_KEY = "".join([choice(
        "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^*-_=+") for i in range(50)])

JWT_SECRET_KEY = SECRET_KEY
JWT_ALGORITHM = 'HS256'

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'debug_toolbar',
    # Uncomment the next line to enable the admin:
    'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
    'rest_framework',
    'django_countries',
    'saas',
    'rules',
    'testsite'
)

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'testsite.wsgi.application'
ROOT_URLCONF = 'testsite.urls'

MIDDLEWARE = (
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'testsite.authentication.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware'
)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DB_NAME,
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'testsite.authentication.JWTAuthentication',
        # `rest_framework.authentication.SessionAuthentication` is the last
        # one in the list because it will raise a PermissionDenied if the CSRF
        # is absent.
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS':
        'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'ORDERING_PARAM': 'o',
    'SEARCH_PARAM': 'q'
}

# Static files (CSS, JavaScript, Images)
MEDIA_ROOT = os.path.join(BASE_DIR, 'testsite', 'media')
MEDIA_URL = '/media/'

APP_STATIC_ROOT = os.path.join(BASE_DIR, 'testsite', 'static')
STATIC_URL = '/static/'

if DEBUG:
    STATIC_ROOT = ''
    # Additional locations of static files
    STATICFILES_DIRS = (APP_STATIC_ROOT,)
else:
    STATIC_ROOT = APP_STATIC_ROOT

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)


MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'
MESSAGE_TAGS = {
    messages.ERROR: 'danger'
}

DEBUG_TOOLBAR_PATCH_SETTINGS = False
DEBUG_TOOLBAR_CONFIG = {
    'JQUERY_URL': '/static/vendor/jquery.js',
    'SHOW_COLLAPSED': True,
    'SHOW_TEMPLATE_CONTEXT': True,
}

INTERNAL_IPS = ('127.0.0.1', '::1')

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


LOGIN_URL = reverse_lazy('login')
LOGIN_REDIRECT_URL = reverse_lazy('product_default_start')

# Allow user to enter month in durationfield
DURATIONFIELD_ALLOW_MONTHS = True

# Configuration of djaodjin-saas
SAAS = {
  'BROKER': {
      'GET_INSTANCE': 'cowork',
  },
  'PLATFORM_NAME': 'cowork',
  'PROCESSOR': {
      'BACKEND': 'saas.backends.stripe_processor.StripeBackend',
      'MODE': 0, # `LOCAL`
      'PRIV_KEY': getattr(sys.modules[__name__], "STRIPE_PRIV_KEY", None),
      'PUB_KEY': getattr(sys.modules[__name__], "STRIPE_PUB_KEY", None),
      'CLIENT_ID': getattr(sys.modules[__name__], "STRIPE_CLIENT_ID", None),
      'WEBHOOK_SECRET': getattr(
          sys.modules[__name__], "STRIPE_ENDPOINT_SECRET", None),
# Comment above and uncomment below to use RazorPay instead.
#      'BACKEND': 'saas.backends.razorpay_processor.RazorpayBackend',
#      'PRIV_KEY': getattr(sys.modules[__name__], "RAZORPAY_PRIV_KEY", None),
#      'PUB_KEY': getattr(sys.modules[__name__], "RAZORPAY_PUB_KEY", None),
    },
    'EXPIRE_NOTICE_DAYS': [90, 60, 30, 15, 1],
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
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'formatters': {
        'simple': {
            'format': 'X X %(levelname)s [%(asctime)s] %(message)s',
            'datefmt': '%d/%b/%Y:%H:%M:%S %z'
        },
    },
    'handlers': {
        'log': {
            'level':'DEBUG',
            'formatter': 'simple',
            'class':'logging.StreamHandler',
        },
        'db_log': {
            'level': 'DEBUG',
            'formatter': 'simple',
            'filters': ['require_debug_true'],
            'class':'logging.StreamHandler',
        },
    },
    'loggers': {
        'rules': {
            'handlers': [],
            'level': 'INFO',
        },
        'saas': {
            'handlers': [],
            'level': 'INFO',
        },
#        'django.db.backends': {
#             'handlers': ['db_log'],
#             'level': 'DEBUG',
#             'propagate': True,
#        },
        'django.request': {
            'handlers': [],
            'level': 'ERROR',
        },
        # If we don't disable 'django' handlers here, we will get an extra
        # copy on stderr.
        'django': {
            'handlers': [],
        },
        # This is the root logger.
        # The level will only be taken into account if the record is not
        # propagated from a child logger.
        #https://docs.python.org/2/library/logging.html#logging.Logger.propagate
        '': {
            'handlers': ['log'],
            'level': 'WARNING'
        }
    }
}
if logging.getLogger('gunicorn.error').handlers:
    LOGGING['handlers']['log'].update({
        'class':'logging.handlers.WatchedFileHandler',
        'filename': LOG_FILE
    })


# Templates (Django 1.8+)
# ----------------------
if TEMPLATE_REVERT_TO_DJANGO:
    sys.stderr.write("Use Django templates engine.\n")
    TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': (os.path.join(BASE_DIR, 'testsite', 'templates'),
                 os.path.join(BASE_DIR, 'saas', 'templates')),
        'OPTIONS': {
            'context_processors': [
    'django.contrib.auth.context_processors.auth', # because of admin/
    'django.contrib.messages.context_processors.messages', # because of admin/
    'django.template.context_processors.request',
    'django.template.context_processors.media',
    'testsite.context_processors.js_framework'
            ],
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader'],
            # XXX 'builtins' key is not supported on Django 1.8
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
