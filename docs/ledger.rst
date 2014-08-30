Transactions
============

Transactions are recorded in an append-only double-entry book keeping ledger
using the following Model

================= ===========
Name              Description
================= ===========
created_at        Date of creation
amount            Amount in cents
orig_account      Source account
dest_account      Target account
orig_organization Source ``Organization``
dest_organization Target ``Organization``
descr             Free-form text description (optional)
event_id          Tie-in to third-party payment processor at the origin
                  of the transaction (optional)
================= ===========

A ``Transaction`` records the movement of an *amount* from a *customer*
Organization's account to a *provider* Organization's account. When actual
charges are generated, a third-party processor organization is also involved.
The customer and provider are potentially identical when an amount is moved
from one account to another account within the same Organization.

Accounts
--------

Each organization has exactly 6 accounts: Income, Assets, Payable, Refund,
Chargeback and Writeoff.

These accounts are used to create a provider's balance sheet from
the ``Transaction`` table which contains the following information:

- Assets
    Cash amount currently held by the provider.
- Income
    Total amount paid to the provider for services.
- Expenses
    These includes Refund, Chargeback and Writeoff which were paid
    back to clients.
- (Liabilities)
    In a marketplace scenario, these *Payable* are invoices that were billed
    to the provider, acting as a client, that have not been settled yet.

These accounts are also used to create a "valuable client" payment profile
as such for example:

- Value
    The total amount invoiced for services to the client.
- *Payable*
    Amount currenly payable by the client to providers for services
    that has not been settled yet.
- Acquisition and Retention
    Amount for free trials and other goodies given to the client at
    a provider's initiative.
- Dispute
    Amount that refunded, charged back or written off in association
    with services provided to the client.

Records
-------

.. image:: transactions.*

Transactions make a state diagram that represent
the following actions.

Use of Service
^^^^^^^^^^^^^^

Each time a provider delivers a service to a customer, a transaction is recorded
that goes from the provider ``Income`` account to the customer ``Payable``
account.

    yyyy/mm/dd description
               customer:Payable                       amount
               provider:Income

Charge Created
^^^^^^^^^^^^^^

When a charge through the payment processor is sucessful, a transaction is
created from customer payable to provider assets and processor income (fee).

    yyyy/mm/dd description
               provider:Assets        amount_minus_fee
               processor:Income       processor_fee
               customer:Payable

From an implementation standpoint, two ``Transaction`` records are created,
one for the provider and one for the processor.

Refund and Chargeback
^^^^^^^^^^^^^^^^^^^^^

Refunds are initiated initiated by the provider while chargebacks are initated
by the customer. In either case, they represent a loss of income while the service
was provided.

    yyyy/mm/dd description
               customer:*payback*     amount
               processor:Income     processor_fee
               provider:Assets

From an implementation standpoint, two ``Transaction`` records are created,
one for the provider and one for the processor.

Stripe allows you to issue a refund at any time
`up to 90 days <https://support.stripe.com/questions/how-do-i-issue-refunds>`_
after the charge while for most transactions, customers have
`120 days from the sale <http://www.cardfellow.com/blog/chargebacks/>`_
or when they discovered a problem with the product to dispute a charge.

Write off
^^^^^^^^^

Sometimes, a provider will give up and assume payables cannot be recovered
from a customer. At that point a writeoff transaction is recorded in order
to keep the ledger balanced.

    yyyy/mm/dd description
               customer:Writeoff       amount
               customer:Payable

Charges
-------

Charges are recorded in a table separate from the ledger. They undergo
their own state diagram as follows.

.. image:: charges.*



