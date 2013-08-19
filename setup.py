from distutils.core import setup

setup(
    name='saas_framework',
    version='0.1',
    author='Fortylines LLC',
    author_email='support@fortylines.com',
    packages=['saas','saas.views','saas.static','saas.backends','saas.management','saas.management','saas.urls','saas.templatetags','saas.templates','saas.migrations'],
    url='https://github.com/fortylines/saas_framework/',
    license='LICENSE',
    description='Fortylines SaaS implementation',
    long_description=open('README.md').read(),
)
