HTML pages
==========

URLs serving HTML pages are split in two sets: subscriber-facing and
provider-facing pages.

If you want to present a completely different user interface to customers
and managers of the provider backend, you will choose to have both
sets of templates inherit from a different base template. If you are building
an interface where managers see an augmented interface overlayed on top of
regular subscriber interface, you might prefer all your templates to inherit
from a common base template.

Subscriber facing pages
-----------------------

All the pages in this group are accessible to a subscriber, either to establish
a relationship with the site by subscribing to a plan or to manage her billing
profile, active subscriptions, etc.

You will want to edit these templates first since they directly impact the
look and feel a customer will have of your site.

Create a subscription
^^^^^^^^^^^^^^^^^^^^^

.. http:get:: /legal/

.. autoclass:: saas.views.legal.AgreementListView


.. http:get:: /legal/:agreement/

.. autoclass:: saas.views.legal.AgreementDetailView


.. http:get:: /legal/:agreement/sign
.. http:post:: /legal/:agreement/sign

.. autoclass:: saas.views.legal.AgreementSignView


.. http:get:: /pricing/
.. http:post:: /pricing/

.. autoclass:: saas.views.plans.CartPlanListView


.. http:get:: /redeem/

.. autoclass:: saas.views.billing.RedeemCouponView

.. _pages_cart:

.. http:get:: /billing/cart/
.. http:get:: /billing/:organization/cart/
.. http:post:: /billing/:organization/cart/

.. automethod:: saas.views.billing.CartView.get


.. http:get:: /billing/:organization/cart-periods/
.. http:post:: /billing/:organization/cart-periods/

.. autoclass:: saas.views.billing.CartPeriodsView


.. http:get:: /billing/:organization/cart-seats/
.. http:post:: /billing/:organization/cart-seats/

.. autoclass:: saas.views.billing.CartSeatsView


.. http:get:: /billing/:organization/receipt/:charge

.. autoclass:: saas.views.billing.ChargeReceiptView


.. http:get:: /app/new/

.. autoclass:: saas.views.profile.OrganizationCreateView


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

.. http:get:: /billing/:organization/

.. autoclass:: saas.views.billing.BillingStatementView


.. http:get:: /billing/:organization/balance/
.. http:post:: /billing/:organization/balance/

.. automethod:: saas.views.billing.BalanceView.get_queryset


.. http:get:: /billing/:organization/card/
.. http:post:: /billing/:organization/card/

.. autoclass:: saas.views.billing.CardUpdateView


.. http:get:: /profile/:organization/
.. http:post:: /profile/:organization/

.. autoclass:: saas.views.profile.OrganizationProfileView


.. http:get:: /profile/:organization/subscriptions/

.. autoclass:: saas.views.profile.SubscriptionListView


.. http:get:: /profile/:organization/roles/managers/
.. http:get:: /profile/:organization/roles/contributors/

.. autoclass:: saas.views.profile.RoleListView


.. http:get:: /users/roles/
.. http:get:: /users/:user/roles/

.. autoclass:: saas.views.users.ProductListView


Provider facing pages
---------------------

Provider facing pages are only accessible to its managers.
They are used to assess the performance of the business,
set pricing strategy, and help with customer support.

Pricing strategy
^^^^^^^^^^^^^^^^

.. http:get:: /provider/billing/coupons/
.. http:get:: /provider/billing/:organization/coupons/

.. autoclass:: saas.views.billing.CouponListView

.. http:get:: /provider/profile/plans/new/
.. http:get:: /provider/profile/:organization/plans/new/
.. http:post:: /provider/profile/:organization/plans/new/

.. autoclass:: saas.views.plans.PlanCreateView

.. http:get:: /provider/profile/plans/:plan/
.. http:get:: /provider/profile/:organization/plans/:plan/

.. autoclass:: saas.views.plans.PlanUpdateView


Transfer subscriber payments to provider bank
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. _pages_provider_transactions:

.. http:get:: /provider/billing/bank/
.. http:get:: /provider/billing/:organization/bank/

.. autoclass:: saas.views.billing.BankUpdateView

.. http:get:: /provider/billing/transfers/
.. http:get:: /provider/billing/:organization/transfers/

.. autoclass:: saas.views.billing.TransferListView

.. http:get:: /provider/billing/import/
.. http:get:: /provider/billing/:organization/import/

.. autoclass:: saas.views.billing.ImportTransactionsView


Manage subscribers and business performance
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. http:get:: /provider/metrics/coupons/:coupon
.. http:get:: /provider/metrics/:organization/coupons/:coupon

.. autoclass:: saas.views.metrics.CouponMetricsView


.. http:get:: /provider/metrics/dashboard/
.. http:get:: /provider/metrics/:organization/dashboard/

.. autoclass:: saas.views.profile.DashboardView


.. http:get:: /provider/metrics/plans/
.. http:get:: /provider/metrics/:organization/plans/

.. autoclass:: saas.views.metrics.PlansMetricsView


.. http:get:: /provider/metrics/revenue/
.. http:get:: /provider/metrics/:organization/revenue/

.. autoclass:: saas.views.metrics.RevenueMetricsView


.. http:get:: /provider/profile/subscribers/
.. http:get:: /provider/profile/:organization/subscribers/

.. autoclass:: saas.views.profile.SubscriberListView


.. http:get:: /provider/metrics/balances/:report/

.. autoclass:: saas.views.metrics.BalancesView

