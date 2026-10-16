# observability

Kind: **optional**. Default: **off**. Setting: `MODULE_OBSERVABILITY_ENABLED`.

Package: `modular_forge.observability`. Dependencies: none.

## Behavior

Opt-in Sentry FastAPI integration with PII/request/breadcrumb and exception-message scrubbing.

## Owned surface

Tables/collections: none.

Routes: No public error-trigger or verification route.

## Disable or remove

Extra: observability. Remove observability/, registry/toggle/settings/tests/extra. Review any custom telemetry before replacing the adapter.

A toggle does not delete database objects or dependency extras. Follow [the modular plan](../MODULAR_PLAN.md), keep old migrations immutable, and run enabled/disabled, boundary and relevant provider contract tests after changes.
