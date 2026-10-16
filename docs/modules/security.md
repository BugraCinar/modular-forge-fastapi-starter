# security

Kind: **required**. Default: **on**. Setting: `Required; no toggle`.

Package: `modular_forge.security`. Dependencies: identity.

## Behavior

Argon2id with pepper, explicit JWT validation, current account/role authorization, signed CSRF and security/error headers.

## Owned surface

Tables/collections: none.

Routes: Dependencies and middleware cover all API routes.

## Disable or remove

Required. Weakening this boundary needs a reviewed replacement and regression tests.

A toggle does not delete database objects or dependency extras. Follow [the modular plan](../MODULAR_PLAN.md), keep old migrations immutable, and run enabled/disabled, boundary and relevant provider contract tests after changes.
