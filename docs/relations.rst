Roles, Subscriptions and Opt-ins
================================

There exists two types of relationships in djaodjin-saas:

- between users and organizations (ex: donny is a manager of cowork)
- between organizations themselves (ex: cowork is a subscriber of djaodjin)

.. image:: relations.*


A ``Role`` connects a ``User`` to an ``Organization`` through
a ``RoleDescription``. A ``Subscription`` connects an ``Organization``
to another ``Organization`` through a ``Plan``
(see :doc:`database schema <models>`).

In both cases granting a new relationship will invite a ``User``
(or ``Organization``) to the site or ask the ``User`` (or ``Organization``)
to opt-in into the relationship as necessary.

Connecting a User to an Organization
------------------------------------

Grant of a role to an organization must be initiated by a user who has
an existing relationship to the Organization and permissions to grant the
new role. (see :doc:`Flexible Security Framework <security>`).

The grant mechanism is also used to invite people to register to the site.
Because users might have multiple e-mail addresses, already registered
with one address yet invited on another, the first authenticated user
that claims the ``grant_key`` will be associated with the ``Role``.

Request for a role initiated by a user who has no pre-existing relationship
to the organization will trigger a notification to all managers
of the organization. A manager then has the opportunity to then accept
the request and grant any ``RoleDescription`` to the requesting user.

As ``grant_key`` are random 40-characters long hexadecimal strings,
it is virtually impossible for a random user to claim a grant unauthorized,
yet gives an opportunity to already registered users to easily consolidate
their accounts under a single sign-on.

In case an organization prefers to avoid the (minimal) risk of a grant key
being intercepted, a manager can instructs a user to register an account on
the site and request a role to the organization. Since in many cases the
organization manager knows best which role to grant the requesting user,
the ``RoleDescription`` is not part of the request but part of the accept.

We are always looking for feedback and new use cases. If you are building
a SaaS product that requires much more strident identity
checks on grants, please `get in touch with us <https://djaodjin.com/contact/>`_
.

.. image:: role-grant-request.*


Connecting Two Organizations to each other
------------------------------------------

In ninety-nine percent of the cases, two organizations become connected
together when one subscribes to a plan provided by the second through
the :doc:`orders<checkout page>`.

There are two special cases. First, a provider can decide to directly grant
a subscription to a plan for multiple reasons (ex: demo, invite-only plans,
fixing a mistaken purchase from a customer). Second, even though
a customer can subscribe and pay online, some plans require a setup and/or
activation from the provider (ex: assign a desk at a co-working space).

In all cases where a provider subscribes an organization to one of its plan,
there needs to be an opt-in from the new subscriber. This is because managers
of the provider will then have access to profile information of the subscriber
for support reasons (see :doc:`Flexible Security Framework <security>`).
The only exception is the broker organization (i.e. organization hosting
the site) since the hosting service reliability team typically have direct
access to the underlying database already.

We decided that charges happen at checkout even for ``Plan`` that require
managers of the provider to accept the subscription (i.e.
``Plan.optin_on_request = True``). If your business logic requires to charge
after the subscription has been accepted by a provider's manager,
please `get in touch with us <https://djaodjin.com/contact/>`_.
We are always looking for feedback and new use cases.
