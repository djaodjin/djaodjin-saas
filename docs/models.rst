Authorization Model
===================

*Organization*s form a single tree through the *parent* relationship. The root
Organization tree is typically the owner of the top-level domain service.

By definition a *User* that has authorization to a node has identical
authorization to the sub-tree rooted at that node.

The model defines two roles for the Organization/User relationship:
*Contributor* and *Manager*.

Contributors have read-only permissions to an Organization sub-tree. This
does not mean they cannot modify fields and models as the application logic
requires, just that they cannot change Organization and User relationships
rooted at the Organization node they contribute too.

Managers are contributors with the explicit permissions to:
- Add an Organization in a previsouly existing Organization subtree.
- Add Contributors to an Organization
- Add Managers to an Organization

Transactions
============

Transactions are recorded in an append-only double-entry book keeping ledger.

    created_at:        Date of creation
    amount:            Amount in cents
    orig_account:      Origin account
    dest_account:      Dest account
    orig_organization: Origin Organization
    dest_organization: Dest Organization

    (Optional: descr and event_id)



