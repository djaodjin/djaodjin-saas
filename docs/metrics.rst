Metrics
=======

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
