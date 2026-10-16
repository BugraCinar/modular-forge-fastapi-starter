# Modular Forge — FastAPI

[![CI](https://github.com/BugraCinar/modular-forge-fastapi-starter/actions/workflows/ci.yml/badge.svg)](https://github.com/BugraCinar/modular-forge-fastapi-starter/actions/workflows/ci.yml)
[![Dependency audit](https://github.com/BugraCinar/modular-forge-fastapi-starter/actions/workflows/dependency-audit.yml/badge.svg)](https://github.com/BugraCinar/modular-forge-fastapi-starter/actions/workflows/dependency-audit.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
[![License: CC0](https://img.shields.io/badge/license-CC0--1.0-lightgrey)](LICENSE)

A security-focused FastAPI REST API starter organized as removable feature modules. The Python sibling of [Modular Forge Spring Boot](https://github.com/BugraCinar/modular-forge-spring-boot-starter), with the same emphasis on clear module boundaries, replaceable adapters and deployment-safe defaults.

## Included

- JWT access tokens, current account/role validation and rotating opaque refresh tokens with replay revocation
- Argon2id password hashing with an independent application pepper
- Email verification, password reset/change, verified email changes, account lockout and optional reCAPTCHA
- Signed CSRF protection for HttpOnly browser refresh cookies; body-token contract for API/mobile clients
- USER / ADMIN / SUPER_ADMIN authorization, profile management, session revocation and audit records
- Optional encrypted TOTP 2FA, Cloudflare R2 image storage, encrypted database backups, Sentry and Kafka events
- PostgreSQL, MySQL, MariaDB and MongoDB adapters; SQLite for infrastructure-free local development
- Alembic migrations, Docker/Compose, public module discovery and documented physical removal
- Unit/integration, security regression, module-boundary and physical-removal tests; real database contracts in CI
- Python 3.11–3.14 CI, dependency audits and CodeQL

This is a modular monolith: one application, feature-owned packages and shared ports. Routes using synchronous drivers run in FastAPI's thread pool. Read [architecture and differences from Spring Boot](docs/ARCHITECTURE.md) before treating it as an API-compatible replacement.

## Quick start

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/getting-started/installation/). No database server or Redis is required for the default local smoke run.

```bash
git clone https://github.com/BugraCinar/modular-forge-fastapi-starter.git
cd modular-forge-fastapi-starter
uv sync --locked --all-extras
uv run --no-sync modular-forge init-env
uv run --no-sync modular-forge migrate
uv run --no-sync uvicorn modular_forge.app:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers --no-server-header
```

The same commands work in PowerShell. `init-env` refuses to overwrite an existing file and generates independent random secrets; the resulting `.env` is ignored by git. The local template selects SQLite, the development-only memory rate limiter, HTTP-compatible cookies and Swagger UI. Production validation rejects those unsafe deployment shortcuts.

Open `http://127.0.0.1:8000/docs`, `/health/ready` or `/api/v1/modules`.

Create your first verified super administrator interactively:

```bash
uv run --no-sync modular-forge create-admin --email admin@example.com --username local_admin
```

The command prompts for a password and confirmation; passwords are not command-line arguments. Login with JSON `{"username":"local_admin","password":"your-password"}` at `POST /api/v1/auth/login` and use the returned bearer token.

Without uv, create/activate a virtual environment and install with `python -m pip install ".[dev,postgresql,mysql,mongodb,two-factor,image-storage,database-backup,observability,kafka]"`; then run the management/uvicorn commands directly. Production deployments can install only the extras they need, for example `python -m pip install ".[postgresql]"`.

## Email and browser authentication

SMTP is deliberately off in the default local environment. Configure `MODULE_EMAIL_ENABLED=true`, `MAIL_HOST`, sender and credentials before using registration/verification/reset delivery. No raw verification/reset tokens are printed or returned by the API. Disabled delivery fails explicitly; tests inject an in-memory notification port. For local email testing, use a dedicated test SMTP server and disable STARTTLS only in development if that server requires it.

Browser clients send `use_cookie: true` on login. The refresh token then stays in an HttpOnly cookie and is omitted from the JSON response. Echo the CSRF cookie value in `X-XSRF-TOKEN` when calling refresh/logout. `GET /api/v1/auth/csrf` can issue a signed CSRF value. API/mobile clients leave `use_cookie` false and send `{"refresh_token":"..."}` to refresh/logout without browser cookie authority.

## Modules

`GET /api/v1/modules` reports all 15 modules, activation state, dependencies, environment toggle and guide. The complete matrix is in [docs/MODULES.md](docs/MODULES.md).

```dotenv
MODULE_TWO_FACTOR_ENABLED=false
MODULE_IMAGE_STORAGE_ENABLED=false
MODULE_DATABASE_BACKUP_ENABLED=false
MODULE_OBSERVABILITY_ENABLED=false
MODULE_KAFKA_ENABLED=false
```

External SDKs are optional extras and load only when their feature is enabled. TOTP/backup keys and R2/Kafka/Sentry credentials are validated before use. Disabling a module removes its runtime surface; deleting it also requires dependency/configuration/schema cleanup. [Add/remove rules](docs/MODULAR_PLAN.md) and the 15 [module guides](docs/modules/) describe ownership and migration steps.

## Database and Docker

Set `DATABASE_URL` and install the selected extra. SQL uses the same transaction port as MongoDB; MongoDB requires a replica set. [Provider URLs, TLS and migrations](docs/DATABASES.md).

The Compose file is a **local development** PostgreSQL + Redis stack:

```bash
docker compose up -d postgres redis
docker compose --profile api run --rm api modular-forge migrate
docker compose --profile api up --build -d api
```

Run schema migrations as a controlled deployment step before starting API replicas. The base Docker image includes the PostgreSQL driver and runs as a non-root user. Other extras and external backup utilities must be installed in a derived image when needed.

## Verify

```bash
uv run --frozen --all-extras ruff check .
uv run --frozen --all-extras ruff format --check .
uv run --frozen --all-extras mypy src/modular_forge
uv run --frozen --all-extras pytest --cov=modular_forge
uv run --frozen --all-extras pip-audit --local --skip-editable
uv run --frozen --all-extras python -m build
```

CI runs real contracts against PostgreSQL, MySQL, MariaDB and a MongoDB replica set, plus clean wheel installation and Docker build checks. Locally, four external-provider test cases skip unless `CONTRACT_DATABASE_URL` points at a disposable `forge_contract` database. Dependency audit also runs weekly. Commit `uv.lock` updates and rerun audits when changing dependencies.

## Deployment notes

- Read the [security model](docs/SECURITY.md). Set `ENVIRONMENT=production`, explicit allowed hosts/HTTPS origins, Secure cookies, verified database TLS and fail-closed `rediss://` rate limiting.
- API docs, seed accounts and schema auto-create are forbidden in production. Startup never supplies default secrets.
- Keep trusted-edge TLS and proxy/client-IP handling explicit; the server command ignores forwarding headers by default.
- Run `modular-forge cleanup` from an external scheduler for expired tokens/challenges and old audit events.
- SMTP/Kafka/audit delivery is best effort, with documented after-commit behavior. Add a durable transactional outbox when your delivery requirements need it.
- Logout revokes refresh families; existing access JWTs may last until their short expiry. Security-sensitive account changes and refresh reuse revoke access through auth-version.
- Encrypted backups still contain sensitive data. Plan retention, key recovery, restore rehearsals and filesystem quotas. TOTP has no unauthenticated recovery bypass.

## License

Released under [CC0 1.0](LICENSE), matching the Spring Boot sibling.
