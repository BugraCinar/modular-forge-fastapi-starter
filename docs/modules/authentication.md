# authentication

Kind: **required**. Default: **on**. Setting: `Required; no toggle`.

Package: `modular_forge.auth`. Dependencies: identity, security, rate-limit.

## Behavior

JWT login, registration/verification, password reset/change, refresh rotation, cookie CSRF, sessions and verified email changes.

## Owned surface

Tables/collections: auth_tokens.

Routes: /api/v1/auth/*

## Disable or remove

Consumes NotificationGateway, SecondFactorGateway, AuditGateway and EventGateway from shared/ports.py. Keep these contracts when replacing adapters.

A toggle does not delete database objects or dependency extras. Follow [the modular plan](../MODULAR_PLAN.md), keep old migrations immutable, and run enabled/disabled, boundary and relevant provider contract tests after changes.
