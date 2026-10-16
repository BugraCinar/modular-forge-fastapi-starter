# Architecture

One FastAPI deployment, with feature packages and explicit dependency boundaries:

```text
HTTP -> request limits + security headers + host/CORS validation
     -> auth / admin / profile / optional feature routes
     -> identity + shared transaction and adapter ports
          -> SQLAlchemy Core or PyMongo
          -> SMTP / TOTP / audit / R2 / Kafka
```

The application factory is the composition root. It loads optional implementations by registry name only when enabled. Lifespan initializes persistence, starts Kafka/seed opt-ins, and closes shared resources. Route handlers using blocking I/O are normal `def` functions, so FastAPI runs them in its thread pool. This is a deliberate synchronous starter, not an application that calls synchronous drivers inside async request handlers.

`shared/persistence.py` defines a small unit-of-work interface. Both providers implement commit/rollback, normalized filters, unique constraints and revision-based compare-and-set updates. SQL also locks rows for security-sensitive flows. MongoDB requires transactions on a replica set or sharded cluster; standalone MongoDB is rejected. Transient write conflicts fail the operation rather than issuing duplicate credentials; clients may retry an ordinary conflict response.

Identity owns a single account table with USER, ADMIN and SUPER_ADMIN roles. Profiles, encrypted TOTP credentials/challenges, audit events and backup jobs belong to their feature modules. Optional feature state does not become columns on the shared account model.

Access JWTs include an explicit algorithm, issuer, audience, subject, role, token type, expiry and account auth-version. Protected requests read current account state. Password, email, role, lockout and TOTP credential changes invalidate prior access/refresh credentials. Refresh tokens are opaque and only keyed hashes are stored. Rotation consumes the previous token atomically; reuse invalidates the account's sessions through auth-version.

Notification and event callbacks run after database commit. SMTP failure can return 503 after an account/token was persisted; resend workflows are provided. Kafka is best-effort after-commit delivery, not a durable outbox or exactly-once guarantee. Audit delivery is also best effort and emits a credential-free operational error on failure. Applications requiring guaranteed notification/event/audit delivery should add a transactional outbox and a durable worker.

Maintenance runs through `modular-forge cleanup` and an external scheduler. There are no per-worker background timers that could duplicate jobs across API replicas.

## Differences from the Spring Boot sibling

- Python-native package structure, Pydantic settings, FastAPI dependencies, SQLAlchemy Core and Alembic replace Spring/JPA/Flyway.
- SQLite is the local smoke/test provider corresponding to the Java starter's H2 use case.
- Accounts share one identity model; there are no separate Java User/Admin entity hierarchies.
- Request/response fields use Python snake_case. This is feature parity, not a wire-compatible replacement.
- SMTP is off in the default local template. Install/configure a notification provider before registration/reset delivery; tokens are never printed as a development shortcut.
- Encrypted backups are downloaded by a reauthenticated SUPER_ADMIN. Emailing entire database dumps is intentionally not the default transport. External dump utilities must be installed for non-SQLite providers.
- Maintenance is explicit CLI work. There is no automatic deletion of deactivated accounts; define retention and recovery policy before adding a purge job.
