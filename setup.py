from distutils.core import setup

from saas import get_version

setup(
    name='saas',
    version=get_version(),
    author='The DjaoDjin Team',
    author_email='support@djaodjin.com',
    packages=['saas',
              'saas.backends',
              'saas.management.commands',
              'saas.migrations',
              'saas.static',
              'saas.templatetags',
              'saas.templates',
              'saas.urls',
              'saas.views',
              ],
    package_data={'saas': ['fixtures/*',
                           'templates/saas/*.html',
                           'templates/saas/agreements/*']},
    url='https://github.com/djaodjin/saas_framework/',
    license='BSD',
    description='DjaoDjin SaaS implementation',
    long_description=open('README.md').read(),
)
