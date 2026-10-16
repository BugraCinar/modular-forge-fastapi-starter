# admin-management

Kind: **optional**. Default: **on**. Setting: `MODULE_ADMIN_MANAGEMENT_ENABLED`.

Package: `modular_forge.admin`. Dependencies: identity, security.

## Behavior

Paginated account administration with USER/ADMIN/SUPER_ADMIN boundaries and password reauthentication for writes.

## Owned surface

Tables/collections: none; uses identity accounts.

Routes: /api/v1/admin/users and /users/{id}/password

## Disable or remove

Remove admin/ and its toggle/registry/routes/tests. Do not drop accounts: identity and authentication own those records.

A toggle does not delete database objects or dependency extras. Follow [the modular plan](../MODULAR_PLAN.md), keep old migrations immutable, and run enabled/disabled, boundary and relevant provider contract tests after changes.
