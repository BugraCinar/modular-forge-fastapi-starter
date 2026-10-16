# Modular plan

The registry in `modules/catalog.py` is the source of runtime module discovery at `GET /api/v1/modules`.

Required modules are identity, authentication, security and rate limiting. Optional features can be disabled. Replaceable adapters implement a stable consumer/shared port. Toggling a feature off leaves its code, dependency extras and database objects on disk; physical removal is a separate operation.

## Add a feature

1. Create one package owning routes, service, DTOs and `schema.py` as needed.
2. Document owned routes, tables, configuration and dependencies under `docs/modules/`.
3. Add a Boolean setting and a registry entry. External SDKs belong in optional dependency extras and must be imported only when the feature is enabled.
4. If another feature calls it, add the smallest protocol in `shared/ports.py`; inject the port through Runtime. Avoid concrete cross-feature imports.
5. Add a forward migration for SQL and a controlled MongoDB index/data upgrade. Do not edit revision 0001 after release.
6. Add enabled behavior, disabled route, package-boundary and physical-removal tests. Update both environment templates and the module catalog.

## Remove a feature

1. Disable its toggle and check the application starts without its routes/SDK.
2. Read the module guide. Remove the registry entry, owning package and optional dependency extra. Keep consumer-owned ports while a replacement or consumer exists.
3. Remove settings, both environment template entries, feature tests and docs. If a dependency is shared by another feature, retain it.
4. Decide whether data must be retained/exported. Add a new migration dropping only the feature's owned tables/indexes when appropriate; old migrations remain immutable. Back up before destructive schema changes. For MongoDB, drop only the documented collections after retention review.
5. Run the complete verification suite and affected database contracts.

Disabling TOTP while enabled credentials exist is rejected at startup to prevent silently downgrading enrolled accounts. Disable credentials through an authenticated workflow, or follow a separately authorized recovery process, before removing that adapter.
