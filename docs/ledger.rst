Transactions
============

Transactions are recorded in an append-only double-entry book keeping ledger
using the following Model

================= ===========
Name              Description
================= ===========
created_at        Date of creation

orig_account      Source account (Funds, Income, Expenses, etc.)
orig_organization Source ``Organization``
orig_amount       Source amount in ``orig_unit``
orig_unit         Unit of the source amount (defaults to 'usd')

dest_account      Target account (Funds, Income, Expenses, etc.)
dest_organization Target ``Organization``
dest_amount       Target amount in ``dest_unit``
dest_unit         Unit of the target amount (defaults to 'usd')

descr             Free-form text description (optional)
event_id          Tie-in to third-party payment processor at the origin
                  of the transaction (optional)
================= ===========

A ``Transaction`` records the movement of an *amount* from an *source*
to a *target*.

All transactions can be expored in `ledger-cli <http://www.ledger-cli.org>`
format using the export command::

    python manage.py ledger export


In a minimal cash flow accounting system, *orig_account* and *dest_account*
are optional, or rather each ``Organization`` only has one account (Funds)
because we only keep track of the cash transaction.

In a more complex system, we want to keep track of cash assets, revenue
and expenses separately because those numbers are meaningful to understand
the business. The balance sheet we want to generate at the end of each
accounting period will dictate the number of accounts each ``Organization``
has as well as the movements recorded in the double-entry ledger.

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

The balance sheet we are working out off leads to 11 accounts,
9 directly derived from above then 2 more (Withdraw and Writeoff)
to balance the books.

- Expenses
    Payments made by a *subscriber*.
- Funds
    Cash amount currently held on the platform by a *provider*.
- Income
    Taxable income on a *provider* for service provided and invoiced.
- Payable
    Order made by a *subscriber*.
- Refund
    Cash transfer from a *provider*.
- Refunded
    Cash transfer to a *subscriber*.
- Withdraw
    Cash that was taken out of the platform by a *provider*.
- Writeoff
    Receivable that cannot and will not be collected by a *provider*
    (to balance the books).


Place a subscription order from a ``Cart``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automethod:: saas.models.Subscription.create_order


Charge sucessful
^^^^^^^^^^^^^^^^

.. automethod:: saas.models.Charge.payment_successful


Refund and Chargeback
^^^^^^^^^^^^^^^^^^^^^

Refunds are initiated initiated by the *provider* while chargebacks are initated
by the *subscriber*. In either case, they represent a loss of income while the
service was provided.

.. automethod:: saas.models.Charge.refund

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

Period started
^^^^^^^^^^^^^^

.. automethod:: saas.models.Transaction.create_period_started


Withdrawal
^^^^^^^^^^

.. automethod:: saas.models.Organization.withdraw_funds


Write off
^^^^^^^^^

Sometimes, a provider will give up and assume payables cannot be recovered
from a subscriber. At that point a writeoff transaction is recorded in order
to keep the ledger balanced::

            yyyy/mm/dd description
                subscriber:Writeoff                      amount
                subscriber:Payable

Charges
-------

Charges are recorded in a table separate from the ledger. They undergo
their own state diagram as follows.

.. image:: charges.*
