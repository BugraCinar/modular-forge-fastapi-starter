# Repository guide

Read `docs/MODULAR_PLAN.md` and `docs/modules/<module-id>.md` before changing a module.

- Production code lives in `src/modular_forge`. Work inside the owning feature package.
- Only the composition root and module registry select concrete optional implementations. Other features consume the protocols in `shared/ports.py` and the transaction port in `shared/persistence.py`.
- Optional modules must not import one another. Keep their tables in their own schema files; never add optional fields to `accounts`.
- Disabling a module must remove its routes and prevent its SDK/adapter from being loaded. Keep catalog, guides, environment templates and tests synchronized.
- Database changes need a new migration. Never regenerate the committed initial schema snapshot after release. Include a rollback and data-retention note.
- Do not log or commit credentials, raw tokens, passwords, TOTP secrets, backup keys or database URLs. Do not include request bodies in error responses.
- Preserve refresh-token rotation, replay revocation, account auth-version checks, CSRF for cookie authority and fail-closed production rate limits.
- Blocking adapters belong in synchronous FastAPI endpoints or the lifespan thread pool, never directly on the event loop.
- Run `python -m ruff check .`, `python -m ruff format --check .`, `python -m mypy src/modular_forge`, `python -m pytest`, `python -m pip_audit --local --skip-editable` and `python -m build`. CI runs contracts against PostgreSQL, MySQL, MariaDB and MongoDB.
- Preserve unrelated changes. Do not rewrite git history.
