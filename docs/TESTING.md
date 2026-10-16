# Selecting and interpreting tests

Install the locked development environment with `uv sync --frozen --all-extras`.
Run commands from the repository root so source imports and packaged migration
fixtures resolve consistently.

| Change | Focused tests |
|---|---|
| Login, refresh, verification or session behavior | `tests/test_auth.py` |
| JWT, CSRF, account state or HTTP boundaries | `tests/test_security.py` |
| Optional toggles, imports, schema snapshot or physical removal | `tests/test_modules.py` |
| Transaction/filter/provider behavior | `tests/test_persistence.py` |
| Optional feature endpoints | `tests/test_features.py` |
| Adapter behavior and backup credential handling | `tests/test_adapters.py`, `tests/test_backup_config.py` |

```sh
uv run --frozen --all-extras pytest tests/test_auth.py tests/test_security.py
uv run --frozen --all-extras pytest --cov=modular_forge
```

Focused tests help diagnose a change; the complete suite and the checks in
[README](../README.md#verify) remain the final verification. Tests use synthetic
credentials and injected adapters, so SMTP, R2 or Kafka credentials are not needed
for the default run.

## External database contracts

Persistence tests parameterize local SQLite and an external provider. Without
`CONTRACT_DATABASE_URL`, the four external cases skip. Set it only to a disposable
database whose URL contains `forge_contract`; the fixture rejects other names.
It initializes and clears contract data, so never use an application database.
MongoDB contracts additionally require a replica set.

After setting the variable, run `pytest tests/test_persistence.py` through the same
uv command. CI repeats the contracts for PostgreSQL, MySQL, MariaDB and MongoDB.
A skip means the external environment was unavailable, not that its contract
passed. Windows also skips the managed-backup POSIX permission assertion.
