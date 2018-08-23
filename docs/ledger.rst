Transaction ledger
==================

Transactions are recorded in an append-only double-entry book keeping ledger
using the following ``Transaction`` Model:

================= ===========
Name              Description
================= ===========
created_at        Date of creation
descr             Free-form text description (optional)
event_id          Tie-in to other models or third-party systems (optional)

dest_account      Target account (Funds, Income, Expenses, etc.)
dest_organization Target ``Organization``
dest_amount       Target amount in ``dest_unit``
dest_unit         Currency unit of the target amount (defaults to 'usd')

orig_account      Source account (Funds, Income, Expenses, etc.)
orig_organization Source ``Organization``
orig_amount       Source amount in ``orig_unit``
orig_unit         Currency unit of the source amount (defaults to 'usd')
================= ===========

A ``Transaction`` records the movement of an *amount* from an *source*
to a *target*.

All transactions can be expored in `ledger-cli <http://www.ledger-cli.org>`_
format using the export command::

    python manage.py ledger export


In a minimal cash flow accounting system, *orig_account* and *dest_account*
are optional, or rather each ``Organization`` only has one account (Funds)
because we only keep track of the actual transfer of funds.

In a more complex system, like here, we want to keep track of cash assets,
revenue and expenses separately because those numbers are meaningful
to understand the business. The balance sheet we want to generate at the end
of each accounting period will dictate the number of accounts each
``Organization`` has as well as the movements recorded in the double-entry
ledger.

In an online subscription business, there are two chain of events that
trigger ``Transaction`` to be recorded: the
:doc:`subscription pipeline <subscriptions>` itself and the charge pipeline.

subscription pipeline:

- place a subscription order from a ``Cart``
- period start
- period end

charge pipeline:

- charge sucessful
- refund or chargeback (optional)
- refund or chargeback expiration (cannot be disputed afterwards)

Accounts
--------

The balance sheet we are working out of leads to 11 accounts,
9 directly derived from above then 2 more (Withdraw and Writeoff)
to balance the books.

.. image:: accounts.*

- Backlog
    Cash received by a *provider* that was received in advance of earning it.
- Chargeback
    Cash taken back out of a *provider* funds by the platform on a dispute.
- Canceled
    Receivables are written off
- Expenses
    Fees paid by *provider* to a *processor* to settle a credit card payment.
- Funds
    Cash amount currently held on the platform by a *provider*.
- Income
    Taxable income on a *provider* for service provided and invoiced.
- Liability
    Balance due by a *subscriber*.
- Payable
    Order of a subscription to a plan as recorded by a *subscriber*.
- Offline
    Record an offline payment to a *provider* (ex: paper check).
- Receivable
    Order of a subscription to a plan as recorded by a *provider*.
- Refund
    Cash willingly transfered out of a *provider* funds held on the platform.
- Refunded
    Cash transfered back to a *subscriber* credit card.
- Withdraw
    Cash that was taken out of the platform by a *provider*.
- Writeoff
    Payables that cannot and will not be collected by a *provider*

Place a subscription order from a ``Cart``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automethod:: saas.models.TransactionManager.new_subscription_order


Charge sucessful
^^^^^^^^^^^^^^^^

.. automethod:: saas.models.Charge.payment_successful


Refund and Chargeback
^^^^^^^^^^^^^^^^^^^^^

Refunds are initiated by the *provider* while chargebacks are initated
by the *subscriber*. In either case, they represent a loss of income while the
service was provided.

.. automethod:: saas.models.ChargeItem.create_refund_transactions

Stripe allows you to issue a refund at any time
`up to 90 days <https://support.stripe.com/questions/how-do-i-issue-refunds>`_
after the charge while for most transactions, subscribers have
`120 days from the sale <http://www.cardfellow.com/blog/chargebacks/>`_
or when they discovered a problem with the product to dispute a charge.

The provider will incur an extra fee on the chargeback that we record as
such::

            yyyy/mm/dd chargeback fee
                processor:Funds                          chargeback_fee
                provider:Funds

Withdrawal
^^^^^^^^^^

.. automethod:: saas.models.Organization.create_withdraw_transactions


``new_subscription_order`` and ``payment_successful`` generates a seemingly
complex set of ``Transaction``. Now we see how the following events
build on the previously recorded transactions to implement deferred revenue
accounting.

The following events create "accounting" transactions. No actual funds is
transfered between the organizations.

Period started
^^^^^^^^^^^^^^

.. automethod:: saas.models.TransactionManager.create_period_started

Period ended
^^^^^^^^^^^^

.. automethod:: saas.models.TransactionManager.create_income_recognized


Write off
^^^^^^^^^

.. automethod:: saas.models.Organization.create_cancel_transactions


Settled account
^^^^^^^^^^^^^^^

.. automethod:: saas.models.TransactionManager.new_subscription_statement


Charges
-------

Charges are recorded in a table separate from the ledger. They undergo
their own state diagram as follows.

.. image:: charges.*

``ChargeItem`` records every line item for a ``Charge``. The recorded
relationships between ``Charge``, ``ChargeItem`` and ``Transaction.event_id``
is critical to easily record refunds, chargeback disputes and reverted
chargebacks in an append-only double-entry bookkeeping system.
