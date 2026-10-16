# two-factor

Kind: **optional**. Default: **off**. Setting: `MODULE_TWO_FACTOR_ENABLED`.

Package: `modular_forge.twofactor`. Dependencies: identity, authentication.

## Behavior

Encrypted account-bound TOTP enrollment; replay-protected time steps; five-minute, five-attempt, single-use login challenges.

## Owned surface

Tables/collections: two_factor_credentials, two_factor_challenges.

Routes: /api/v1/two-factor/setup, /enable, /disable; auth challenge exchange uses the stable port.

## Disable or remove

Extra: two-factor. Disable enrolled credentials through an authenticated workflow first; startup refuses silent bypass. Remove twofactor/ and its toggle/registry/tests/extra, keep SecondFactorGateway fallback. Add a reviewed sidecar-drop migration after retention review.

A toggle does not delete database objects or dependency extras. Follow [the modular plan](../MODULAR_PLAN.md), keep old migrations immutable, and run enabled/disabled, boundary and relevant provider contract tests after changes.
