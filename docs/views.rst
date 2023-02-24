API and HTML pages
==================

The API is split in four sections:

- `Profiles`_ to manage the identity, such as name or email address,
  of users and organizations registered to the site.

- `Subscriptions`_ to define the relationship between a subscriber and
  a provider through a plan.

- `Billing`_ to manage the checkout, billing and accounting workflows,
  including shopping carts, coupons, charges and balance statements.

- `Metrics`_ to crunch numbers and return various insight
  into the performance of the business.

The HTML Views implement workflows and dashboards pages for subscriber-facing
and provider-facing use cases. The code logic is fully implemented so
progress and redirects happen properly. The HTML templates are minimal
for you to understand how to hook-up the Vue components.

*Design tip*: If you want to present a completely different user interface to
customers and managers of the provider backend, you will choose to have both
sets of templates inherit from a different base template. If you are building
an interface where managers see an augmented interface overlayed on top of
regular subscriber interface, you might prefer all your templates to inherit
from a common base template.

For an example of fully functional pages styled with `Bootstrap`_, take a look
at `DjaoApp default theme`_.


Subscriber facing pages
-----------------------

All the pages in this group are accessible to a subscriber, either to establish
a relationship with the site by subscribing to a plan or to manage her billing
profile, active subscriptions, etc.

You will want to edit these templates first since they directly impact the
look and feel a customer will have of your site.

.. autoclass:: saas.views.legal.AgreementListView

.. autoclass:: saas.views.legal.AgreementDetailView

.. autoclass:: saas.views.legal.AgreementSignView

.. autoclass:: saas.views.plans.CartPlanListView

.. autoclass:: saas.views.billing.RedeemCouponView

.. automethod:: saas.views.billing.CartView.get

.. autoclass:: saas.views.billing.CartPeriodsView

.. autoclass:: saas.views.billing.CartSeatsView

.. autoclass:: saas.views.billing.ChargeReceiptView


Manage subscriptions
^^^^^^^^^^^^^^^^^^^^
.. _pages_subscribers:

These pages enable a subscriber to manage her profile on the site.
She can update her personal information (email address, etc.), change
her credit card on file, review the list of charges by a provider,
pay a balance due, etc.

The business requirements might require or prevent a manager or a custom
role (ex: contributor) of a provider to access specific information about
a subscriber. For example, you might allow your customer support team
to update a subscriber credit card over the phone for convienience.
You might also believe it is too much risk, deny the ability to do so by your
customer support people and instruct them to hand out instructions
to the subscriber on how to do so by herself. All scenarios can easily
be implemented through a :doc:`Flexible Security Framework <security>`.

.. autoclass:: saas.views.billing.BillingStatementView

.. automethod:: saas.views.billing.BalanceView.get_queryset

.. autoclass:: saas.views.billing.CardUpdateView

.. autoclass:: saas.views.profile.OrganizationProfileView

.. autoclass:: saas.views.profile.SubscriptionListView

.. autoclass:: saas.views.profile.RoleListView

.. autoclass:: saas.views.users.ProductListView


Provider facing pages
---------------------

Provider facing pages are only accessible to its managers.
They are used to assess the performance of the business,
set pricing strategy, and help with customer support.

Pricing strategy
^^^^^^^^^^^^^^^^

.. autoclass:: saas.views.billing.CouponListView

.. autoclass:: saas.views.plans.PlanCreateView

.. autoclass:: saas.views.plans.PlanUpdateView


Transfer subscriber payments to provider bank
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. _pages_provider_transactions:

.. autoclass:: saas.views.billing.TransferListView

.. autoclass:: saas.views.billing.ImportTransactionsView


Manage subscribers and business performance
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: saas.views.metrics.CouponMetricsView

.. autoclass:: saas.views.profile.DashboardView

.. autoclass:: saas.views.metrics.PlansMetricsView

.. autoclass:: saas.views.metrics.RevenueMetricsView

.. autoclass:: saas.views.profile.SubscriberListView

.. autoclass:: saas.views.metrics.BalancesView


.. _Profiles: https://www.djaodjin.com/docs/reference/djaoapp/latest/api/#profile

.. _Subscriptions: https://www.djaodjin.com/docs/reference/djaoapp/latest/api/#subscriptions

.. _Billing: https://www.djaodjin.com/docs/reference/djaoapp/latest/api/#billing


.. _Metrics: https://www.djaodjin.com/docs/reference/djaoapp/latest/api/#metrics

.. _Bootstrap: https://getbootstrap.com

.. _DjaoApp default theme: https://www.djaodjin.com/docs/guides/themes/
