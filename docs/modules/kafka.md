# kafka

Kind: **optional**. Default: **off**. Setting: `MODULE_KAFKA_ENABLED`.

Package: `modular_forge.kafka`. Dependencies: none.

## Behavior

Opt-in account.email_changed v1 events keyed by account id, published after database commit. Contains the newly verified email address; secure the broker and retention.

## Owned surface

Tables/collections: none.

Routes: No HTTP routes.

## Disable or remove

Extra: kafka. Remove kafka/, registry/toggle/settings/tests/extra; retain EventGateway/NullEvents. Delivery is best effort with bounded retries, not an outbox or exactly-once guarantee. TLS is required in production.

A toggle does not delete database objects or dependency extras. Follow [the modular plan](../MODULAR_PLAN.md), keep old migrations immutable, and run enabled/disabled, boundary and relevant provider contract tests after changes.
