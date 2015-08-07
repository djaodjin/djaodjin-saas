API Reference
=============

Billing API
-----------

These API end points manage the transfer of funds between a subscriber and
a provider through a processor.

.. http:get:: /api/billing/:organization/bank/

.. autoclass:: saas.api.backend.RetrieveBankAPIView


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

.. _api_billing_payments:

.. http:get:: /api/billing/:organization/payments/

.. autoclass:: saas.api.transactions.TransactionListAPIView

.. _api_billing_transfers:

.. http:get:: /api/billing/:organization/transfers/

.. autoclass:: saas.api.transactions.TransferListAPIView


.. http:get:: /api/billing/charges/:charge/

.. autoclass:: saas.api.charges.ChargeResourceView


.. http:post:: /api/billing/charges/:charge/email/

.. autoclass:: saas.api.charges.EmailChargeReceiptAPIView


.. http:post:: /api/billing/charges/:charge/refund/

.. autoclass:: saas.api.charges.ChargeRefundAPIView


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

.. _api_role:

.. http:get:: /api/profile/:organization/roles/:role/
.. http:post:: /api/profile/:organization/roles/:role/

.. autoclass:: saas.api.users.RoleListAPIView


.. http:delete:: /api/profile/:organization/roles/:role/:user/

.. autoclass:: saas.api.users.RoleDetailAPIView

.. _api_subscriptions:

.. http:get:: /api/profile/:organization/subscriptions/
.. http:post:: /api/profile/:organization/subscriptions/

.. autoclass:: saas.api.subscriptions.SubscriptionListAPIView


.. http:delete:: /api/profile/:organization/subscriptions/<subscribed_plan>/

.. autoclass:: saas.api.subscriptions.SubscriptionDetailAPIView


Metrics API
-----------

.. http:get:: /api/metrics/registered/

.. autoclass:: saas.api.metrics.RegisteredAPIView

.. _api_metrics_subscribers_active:

.. http:get:: /api/metrics/:organization/active/

.. autoclass:: saas.api.subscriptions.ActiveSubscriptionAPIView


.. _api_metrics_balances:

.. http:get:: /api/metrics/:organization/balances/

.. autoclass:: saas.api.metrics.BalancesAPIView


.. _api_metrics_subscribers_churned:

.. http:get:: /api/metrics/:organization/churned/

.. autoclass:: saas.api.subscriptions.ChurnedSubscriptionAPIView


.. _api_metrics_customers:

.. http:get:: /api/metrics/:organization/customers/

.. autoclass:: saas.api.metrics.CustomerMetricAPIView


.. _api_metrics_funds:

.. http:get:: /api/metrics/:organization/funds/

.. autoclass:: saas.api.metrics.RevenueMetricAPIView


.. _api_metrics_plans:

.. http:get:: /api/metrics/:organization/plans/

.. autoclass:: saas.api.metrics.PlanMetricAPIView

