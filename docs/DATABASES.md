# Database providers

Install the selected driver extra; feature code uses the same transaction port for every provider.

| Provider | Install | Development DATABASE_URL |
|---|---|---|
| SQLite | base package | `sqlite:///./modularforge.db` |
| PostgreSQL | `.[postgresql]` | `postgresql+psycopg://user:password@localhost:5432/modularforge` |
| MySQL | `.[mysql]` | `mysql+pymysql://user:password@localhost:3306/modularforge` |
| MariaDB | `.[mysql]` | `mariadb+pymysql://user:password@localhost:3306/modularforge` |
| MongoDB | `.[mongodb]` | `mongodb://localhost:27017/modularforge?replicaSet=rs0` |

Percent-encode database passwords in URLs. Never put real connection strings in README files, CI output or git. MongoDB's database is selected by `MONGODB_DATABASE`; it must match the credential permissions and intended URI database.

Run `modular-forge migrate` before serving. SQL uses versioned, packaged Alembic migrations; revision 0001 includes all optional sidecars so enabling a feature later does not require automatic schema creation. Production startup validates required columns and never creates/updates tables. `AUTO_CREATE_SCHEMA=true` is only an explicit development/test shortcut and must not be mixed with an existing Alembic migration history.

MongoDB migrate creates collections and named unique/secondary indexes idempotently. A replica set or sharded cluster is mandatory. Creating collections/indexes happens outside a transaction; feature writes use transactions. Future incompatible MongoDB upgrades require a reviewed migration job and backup, rather than automatic destructive index replacement.

Production validates transport settings: PostgreSQL `sslmode=verify-full` (plus `sslrootcert` where needed); MySQL/MariaDB `ssl_verify_cert=true&ssl_verify_identity=true` with a trusted CA; MongoDB TLS or SRV. Redis requires `rediss://`. Provision matching trusted certificates and the least-privilege runtime database account. Run migrations with a separate account if runtime DDL is forbidden.

The repository tests verify rollback, after-commit delivery, unique identity constraints, JSON/Boolean round trips, compare-and-set and query injection boundaries. CI runs these contracts against four real providers. Local SQLite success alone does not verify a production provider.

## Schema changes and rollback

Create a new Alembic revision under `persistence/migrations/versions/` and a corresponding MongoDB upgrade procedure. Describe whether old app versions can read the upgraded data. Prefer additive migrations, backfill, then constraint/removal migrations. Downgrading revision 0001 drops all starter tables and loses data; use it only for disposable databases. Never run contract tests against a live database: the test harness requires a `forge_contract` database and creates/removes only its own randomly named table or collection.
