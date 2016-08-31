Database Models
===============

.. automodule:: saas.models

.. image:: saas-models.*

``Organization`` can be semantically separated in four categories, processor,
broker, providers and subscribers.

    * subscribers: organizations that subscribe to one or multiple ``Plan``.
    * providers: organizations that provides plans others can subscribe to.
    * broker: The provider that controls the website.
    * processor: The organization / :doc:`backend <backends>`
      actually processing the charges.

In a pure Software-as-a-Service setup, there is only one provider which is
by definition the broker.

In a marketplace setup, there might be multiple providers even though there
is only one broker, always. The broker controls the domain name on which
the site is hosted.
