API Reference
=============

The djaodjin-saas API is split in four sections: Billing, Subscription, Metrics
and Search.

The Billing and Subscription APIs deal with the actual business logic
of a Software-as-a-Service, that is the transfer of funds and access
control respectively.

The Metrics and Search APIs aggregate the underlying data in various ways
to keep on top of the performance of the business as well as provide rich
interfaces.


Billing API
-----------

These API end points manage the transfer of funds between a subscriber and
a provider through a processor.

.. http:get:: /api/billing/:organization/bank/

.. autoclass:: saas.api.backend.RetrieveBankAPIView


.. _api_billing_payments:

.. http:get:: /api/billing/:organization/billings/

.. autoclass:: saas.api.transactions.BillingsAPIView


.. http:get:: /api/billing/:organization/card/

.. autoclass:: saas.api.backend.RetrieveCardAPIView


.. _api_billing_coupons:

.. http:get:: /api/billing/:organization/coupons/
.. http:post:: /api/billing/:organization/coupons/

.. autoclass:: saas.api.coupons.CouponListAPIView


.. http:get:: /api/billing/:organization/coupons/:coupon/
.. http:put:: /api/billing/:organization/coupons/:coupon/
.. http:delete:: /api/billing/:organization/coupons/:coupon/

.. autoclass:: saas.api.coupons.CouponDetailAPIView


.. http:get:: /api/billing/:organization/receivables/

.. autoclass:: saas.api.transactions.ReceivablesListAPIView


.. _api_billing_transfers:

.. http:get:: /api/billing/:organization/transfers/

.. autoclass:: saas.api.transactions.TransferListAPIView


.. http:get:: /api/billing/transactions/

.. autoclass:: saas.api.transactions.TransactionListAPIView


.. http:get:: /api/billing/charges/:charge/

.. autoclass:: saas.api.charges.ChargeResourceView


.. http:post:: /api/billing/charges/:charge/email/

.. autoclass:: saas.api.charges.EmailChargeReceiptAPIView


.. http:post:: /api/billing/charges/:charge/refund/

.. autoclass:: saas.api.charges.ChargeRefundAPIView


.. _api_cart:

.. http:post:: /api/cart/

.. autoclass:: saas.api.billing.CartItemAPIView


.. http:post:: /api/cart/redeem/

.. autoclass:: saas.api.coupons.CouponRedeemAPIView


.. http:delete:: /api/cart/<plan>/

.. autoclass:: saas.api.billing.CartItemDestroyAPIView


Subscription API
----------------

These API end points manage the subscription logic, payments excluded.


.. http:post:: /api/profile/:organization/plans/

.. autoclass:: saas.api.plans.PlanCreateAPIView


.. http:get:: /api/profile/:organization/plans/<plan>/
.. http:put:: /api/profile/:organization/plans/<plan>/
.. http:delete:: /api/profile/:organization/plans/<plan>/

.. autoclass:: saas.api.plans.PlanResourceView


.. http:put:: /api/profile/:organization/plans/<plan>/activate/

.. autoclass:: saas.api.plans.PlanActivateAPIView


.. http:get::  /api/profile/:organization/
.. http:put::  /api/profile/:organization/
.. http:delete::  /api/profile/:organization/

.. autoclass:: saas.api.organizations.OrganizationDetailAPIView

.. _api_accessibles:

.. http:get:: /api/users/:user/accessibles/
.. http:post:: /api/users/:user/accessibles/

.. autoclass:: saas.api.roles.AccessibleByListAPIView

.. _api_role:

.. http:get:: /api/profile/:organization/roles/:role/
.. http:post:: /api/profile/:organization/roles/:role/

.. autoclass:: saas.api.roles.RoleListAPIView


.. http:delete:: /api/profile/:organization/roles/:role/:user/

.. autoclass:: saas.api.roles.RoleDetailAPIView

.. _api_subscriptions:

.. http:get:: /api/profile/:organization/subscribers/

.. autoclass:: saas.api.organizations.SubscribersAPIView

.. http:get:: /api/profile/:organization/subscriptions/
.. http:post:: /api/profile/:organization/subscriptions/

.. autoclass:: saas.api.subscriptions.SubscriptionListAPIView


.. http:delete:: /api/profile/:organization/subscriptions/<subscribed_plan>/

.. autoclass:: saas.api.subscriptions.SubscriptionDetailAPIView


Metrics API
-----------

.. http:get:: /api/metrics/registered/

.. autoclass:: saas.api.users.RegisteredAPIView

.. _api_metrics_subscribers_active:

.. http:get:: /api/metrics/:organization/active/

.. autoclass:: saas.api.subscriptions.ActiveSubscriptionAPIView


.. _api_metrics_balances:

.. http:get:: /api/metrics/:organization/balances/

.. autoclass:: saas.api.metrics.BalancesAPIView


.. _api_broker_balance_sheets:

.. http:get:: /api/metrics/balances/:report/

.. autoclass:: saas.api.balances.BrokerBalancesAPIView

.. http:get:: /api/metrics/lines/:report/
.. http:post:: /api/metrics/lines/:report/

.. autoclass:: saas.api.balances.BalanceLineListAPIView


.. _api_metrics_subscribers_churned:

.. http:get:: /api/metrics/:organization/churned/

.. autoclass:: saas.api.subscriptions.ChurnedSubscriptionAPIView


.. http:get:: /api/metrics/:organization/coupons/:coupon/

.. autoclass:: saas.api.metrics.CouponUsesAPIView


.. _api_metrics_customers:

.. http:get:: /api/metrics/:organization/customers/

.. autoclass:: saas.api.metrics.CustomerMetricAPIView


.. _api_metrics_funds:

.. http:get:: /api/metrics/:organization/funds/

.. autoclass:: saas.api.metrics.RevenueMetricAPIView


.. _api_metrics_plans:

.. http:get:: /api/metrics/:organization/plans/

.. autoclass:: saas.api.metrics.PlanMetricAPIView


Search API
----------

At times, we might be looking to grant a ``User`` permissions to an
``Organization`` through a ``Role`` (manager, contributor, etc.), or we might
be looking to request access to an ``Organization`` on behalf of a ``User``.
Both features might benefit from an auto-complete suggestions list.
The two following API end point will list all ``Organization`` and ``User``
in the database regardless of their associations.

.. autoclass:: saas.api.organizations.OrganizationListAPIView

.. autoclass:: saas.api.users.UserListAPIView
