# seed-data

Kind: **optional**. Default: **off**. Setting: `MODULE_SEED_DATA_ENABLED`.

Package: `modular_forge.bootstrap`. Dependencies: identity.

## Behavior

Explicit development-only verified SUPER_ADMIN seed. Existing accounts are not overwritten or have their passwords reset.

## Owned surface

Tables/collections: none; inserts identity accounts.

Routes: No HTTP routes; lifespan only.

## Disable or remove

Remove bootstrap/, registry/toggle/seed settings/tests. Do not drop accounts. Production forbids this module; use the interactive create-admin CLI for deployment.

A toggle does not delete database objects or dependency extras. Follow [the modular plan](../MODULAR_PLAN.md), keep old migrations immutable, and run enabled/disabled, boundary and relevant provider contract tests after changes.
