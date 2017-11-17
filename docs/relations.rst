Roles, Subscriptions and Opt-ins
================================

There exists two types of relationships in djaodjin-saas:

- between users and organizations (ex: donny is a manager of cowork)
- between organizations themselves (ex: cowork is a subscriber of djaodjin)


A ``Role`` connects a ``User`` to an ``Organization`` through
a ``RoleDescription``.

A ``Subscription`` connects an ``Organization`` to another ``Organization``
through a ``Plan``.

Connecting a User to an Organization
------------------------------------

- Initiated by an existing manager
- Requested by connected user

Connecting Two Organizations to each other
------------------------------------------

- buying a plan
- initiated by provider

