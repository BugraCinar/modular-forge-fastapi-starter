# Operating the backend

## Startup and readiness

Provision private configuration and run `modular-forge migrate` before starting
API replicas. Startup validates the selected schema and does not apply migrations.
Run migrations as a controlled deployment step with the appropriate database
permissions. See [database configuration](DATABASES.md) for provider details.

`GET /health/live` reports that the process is running. `/health/ready` also checks
the database and rate-limit store; it can return 503 while liveness remains up.
Readiness does not test SMTP, R2, Kafka or other optional external services.

If readiness fails, check database availability, schema state, selected driver,
Redis connectivity and TLS settings using private operational tooling. Do not
weaken production fail-closed rate limiting to make a readiness check pass.

## Scheduled maintenance

Run this command from an external scheduler using the same environment as the API:

```sh
uv run --frozen --all-extras modular-forge cleanup
```

It deletes expired authentication tokens, audit events older than 30 days when
audit is enabled, and expired TOTP challenges when that module is enabled. It does
not purge accounts or provide a general backup-retention policy. Avoid overlapping
maintenance deployments and monitor the scheduler's exit status.

## Deployment changes

Keep module toggles consistent across replicas. A disabled feature loses its
routes; disabling it does not delete its tables or revoke externally stored data.
Read its [module guide](modules/) before removal. Enabled TOTP credentials prevent
silently disabling the TOTP module.

For a deployment rollback, retain compatible configuration and database schema.
Database changes need a separately planned rollback or forward fix; reverting
application code does not undo a migration. Rehearse backup restoration before
relying on it during an incident. [The security guide](SECURITY.md) covers keys,
trusted proxies, transport and cookie settings.
