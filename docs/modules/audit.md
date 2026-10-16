# audit

Kind: **optional**. Default: **on**. Setting: `MODULE_AUDIT_ENABLED`.

Package: `modular_forge.audit`. Dependencies: identity, security.

## Behavior

Credential-free account/admin/authentication action records; administrator-only paginated reads. cleanup removes records older than 30 days.

## Owned surface

Tables/collections: audit_events.

Routes: /api/v1/admin/audit

## Disable or remove

Remove audit/ and its registry/toggle/tests; NullAudit remains in shared ports. Export required audit evidence before a new migration drops the table/collection. Sink delivery is best effort.

A toggle does not delete database objects or dependency extras. Follow [the modular plan](../MODULAR_PLAN.md), keep old migrations immutable, and run enabled/disabled, boundary and relevant provider contract tests after changes.
