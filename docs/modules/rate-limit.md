# rate-limit

Kind: **required**. Default: **on**. Setting: `Required; no toggle`.

Package: `modular_forge.ratelimit`. Dependencies: none.

## Behavior

Atomic Redis INCR/EXPIRE Lua windows; HMAC-derived keys avoid storing raw email/IP identifiers. Memory is development/test only.

## Owned surface

Tables/collections: Redis keys only; no SQL tables.

Routes: Global middleware and account/reauth/email/backup service limits.

## Disable or remove

RedisStore can be replaced behind the hit/healthy/close store contract. Production is fail-closed.

A toggle does not delete database objects or dependency extras. Follow [the modular plan](../MODULAR_PLAN.md), keep old migrations immutable, and run enabled/disabled, boundary and relevant provider contract tests after changes.
