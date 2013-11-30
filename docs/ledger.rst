Subscription Logic
==================

A customer, represented by an ``Organization`` instance later referenced as
*client*, subscribes to services from an ``Organization`` known as *provider*.

.. image:: timeline.*

At the time a client first subscribes to service, a billing cycle is established
for the client. From that time on, a client is billed at the begining of each
billing cycle for all services subscribed to.

In normal business operations, service is available as soon as client
subscribes; service becomes unavailable at the end of a billing cycle.

Whenever potential fraud is detected, that is a client's card is denied
N number of times or a chargeback is created, a client is locked out
immediately.


Transactions
------------

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

A ``Transaction`` records the movement of an *amount* from a *client*
Organization's account to a *provider* Organization's account. When actual
charges are generated, a third-party processor organization is also involved.
The client and provider are potentially identical when an amount is moved
from one account to another account within the same Organization.

Each organization has exactly 6 accounts: Income, Assets, Payable, Refund,
Chargeback and Writeoff.

.. image:: transactions.*

Transactions make a state diagram that represent
the following actions.

Use of Service
^^^^^^^^^^^^^^

Each time a provider delivers a service to a client, a transaction is recorded
that goes from the provider ``Income`` account to the client ``Payable``
account.

    yyyy/mm/dd description
               client:Payable                       amount
               provider:Income

Charge Created
^^^^^^^^^^^^^^

When a charge through the payment processor is sucessful, a transaction is
created from client payable to provider assets and processor income (fee).

    yyyy/mm/dd description
               provider:Assets        amount_minus_fee
               processor:Income       processor_fee
               client:Payable

From an implementation standpoint, two ``Transaction`` records are created,
one for the provider and one for the processor.

Refund and Chargeback
^^^^^^^^^^^^^^^^^^^^^

Refunds are initiated initiated by the provider while chargebacks are initated
by the client. In either case, they represent a loss of income while the service
was provided.

    yyyy/mm/dd description
               client:*payback*     amount
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
from a client. At that point a writeoff transaction is recorded in order
to keep the ledger balanced.

    yyyy/mm/dd description
               client:Writeoff       amount
               client:Payable

Charges
-------

Charges are recorded in a table separate from the ledger. They undergo
their own state diagram as follows.

.. image:: charges.*



