# user-profile

Kind: **optional**. Default: **on**. Setting: `MODULE_USER_PROFILE_ENABLED`.

Package: `modular_forge.profile`. Dependencies: identity, authentication.

## Behavior

Display-name/biography updates, confirmed email changes and account deactivation.

## Owned surface

Tables/collections: profiles.

Routes: /api/v1/profile, /profile/email, /profile/deactivate

## Disable or remove

Remove profile/ and its registry/settings/tests; disable image-storage first. Retain/export profile data, then add a migration dropping profiles if appropriate. Keep account data owned by identity.

A toggle does not delete database objects or dependency extras. Follow [the modular plan](../MODULAR_PLAN.md), keep old migrations immutable, and run enabled/disabled, boundary and relevant provider contract tests after changes.
