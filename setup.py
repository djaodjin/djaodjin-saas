from distutils.core import setup

import saas

setup(
    name='saas',
    version=saas.__version__,
    author='The DjaoDjin Team',
    author_email='support@djaodjin.com',
    packages=['saas',
              'saas.backends',
              'saas.management.commands',
              'saas.migrations',
              'saas.static',
              'saas.templatetags',
              'saas.templates',
              'saas.urls.api',
              'saas.urls.app',
              'saas.views',
              'saas.api',
              ],
    package_data={'saas': ['fixtures/*',
                           'templates/saas/*.html',
                           'templates/saas/agreements/*']},
    url='https://github.com/djaodjin/saas_framework/',
    license='BSD',
    description='DjaoDjin SaaS implementation',
    long_description=open('README.md').read(),
)
