# api-docs

Kind: **optional**. Default: **off**. Setting: `MODULE_API_DOCS_ENABLED`.

Package: `modular_forge.app`. Dependencies: none.

## Behavior

FastAPI OpenAPI/Swagger UI; production validation forbids enabling it.

## Owned surface

Tables/collections: none.

Routes: /docs and /openapi.json; disabled by default settings, enabled by local .env template.

## Disable or remove

Owned by the application factory. Remove its registry entry, module_api_docs_enabled setting, template keys and docs route/CSP configuration from app.py/security middleware. It has no separate SDK or table.

A toggle does not delete database objects or dependency extras. Follow [the modular plan](../MODULAR_PLAN.md), keep old migrations immutable, and run enabled/disabled, boundary and relevant provider contract tests after changes.
