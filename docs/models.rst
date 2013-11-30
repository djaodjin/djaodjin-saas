Authorization Model
===================

*Organizations* form a single tree through the *belongs* relationship. The root
Organization tree is typically the owner of the top-level domain service.

.. image:: security.*

By definition a *User* that has authorization to a node has identical
authorization to the sub-tree rooted at that node.

The model defines two roles for the User/Organization relationship:
*Contributor* and *Manager*.

Contributors have read-only permissions to an Organization sub-tree. This
does not mean they cannot modify fields and models as the application logic
requires, just that they cannot change Organization and User relationships
rooted at the Organization node they contribute too.

Managers possess a superset of the contributors permissions,
with the explicit permissions to:

- Add an Organization in a previsouly existing Organization subtree.
- Add Contributors to an Organization
- Add Managers to an Organization

Implementation Pointers
-----------------------

The function that check User/Organization permissions are implemented
in views/auth.py. They include:

- *valid_contributor_to_organization(user, organization)*

    Returns a tuple (*organization*, *is_manager*) where *organization*
    is an Organization instance and *is_manager* is ``True`` when the
    user is also a manager for the *organization*.

    The functions will raise a ``PermissionDenied`` exception when the
    *user* is neither a contributor nor a manager to the *organization*.

- *valid_manager_to_organization(user, organization)*

    Returns *organization* as an Organization instance if *user*
    is a manager of *organization* and raises a ``PermissionDenied``
    exception otherwise.

To simplify logic that checks permissions, both functions will accept
*organization* to either be an Organization instance or a ``string``
that represents the name of an organization.

The modification of managers and contributors to an organization is
implemented in urls/profile.py (entry point) and views/profile.py (logic).
