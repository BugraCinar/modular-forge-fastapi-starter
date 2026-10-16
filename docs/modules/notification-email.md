# notification-email

Kind: **replaceable**. Default: **off**. Setting: `MODULE_EMAIL_ENABLED`.

Package: `modular_forge.notification`. Dependencies: none.

## Behavior

SMTP STARTTLS delivery through NotificationGateway; reset and verification links are never logged.

## Owned surface

Tables/collections: none.

Routes: No HTTP routes.

## Disable or remove

Remove notification/ and SMTP settings, but keep NotificationGateway and install a working replacement. The disabled fallback explicitly fails delivery; SMTP calls occur after commit and are not durable.

A toggle does not delete database objects or dependency extras. Follow [the modular plan](../MODULAR_PLAN.md), keep old migrations immutable, and run enabled/disabled, boundary and relevant provider contract tests after changes.
