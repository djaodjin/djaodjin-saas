Integration within a multi-app project
======================================

There are two mechanisms to help integrating djaodjin-saas within a project
composed of multiple Django applications.

- Overriding models
- Replacing default functions

For example, `djaoapp`_ is a project which ties djaodjin-saas with other Django
applications into a boilerplate Software-as-a-Service (SaaS) WebApp.


Overriding models
-----------------

Profiles are defined through the `Organization` model. It is often useful
for composition of Django apps to use a single profile model.
This is possible by defining the settings `SAAS_ORGANIZATION_MODEL`.

User/Profile relationships are implemented through the `Role` model.
It is often useful for composition of Django apps to use a single role model.
This is possible by defining the settings `SAAS_ROLE_MODEL`. If you do so, you
will most likely also need to implement a serializer and define
`SAAS['ROLE_SERIALIZER']`.

If the ``AUTH_USER_MODEL`` (as returned by ``get_user_model``) has been
overridden, both ``SAAS['USER_SERIALIZER']`` and
``SAAS['USER_DETAIL_SERIALIZER']`` should be defined and implement a user
model serialization as used in API calls for the summary and detailed contact
information respectively.


Replacing default functions
---------------------------

.. autodata:: saas.settings.BROKER_CALLABLE

.. autodata:: saas.settings.BUILD_ABSOLUTE_URI_CALLABLE

.. autodata:: saas.settings.PICTURE_STORAGE_CALLABLE

.. autodata:: saas.settings.PRODUCT_URL_CALLABLE


.. _djaoapp: https://github.com/djaodjin/djaoapp
