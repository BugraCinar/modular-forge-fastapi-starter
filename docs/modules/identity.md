# identity

Kind: **required**. Default: **on**. Setting: `Required; no toggle`.

Package: `modular_forge.identity`. Dependencies: none.

## Behavior

Required account records with normalized unique email/username, password hashes, account state, roles and auth-version.

## Owned surface

Tables/collections: accounts.

Routes: Consumed by authentication/admin/profile; no independent HTTP routes.

## Disable or remove

No optional adapter. Replacing identity is an architectural fork, not drop-in deletion.

A toggle does not delete database objects or dependency extras. Follow [the modular plan](../MODULAR_PLAN.md), keep old migrations immutable, and run enabled/disabled, boundary and relevant provider contract tests after changes.
