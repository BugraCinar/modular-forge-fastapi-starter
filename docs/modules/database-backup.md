# database-backup

Kind: **optional**. Default: **off**. Setting: `MODULE_DATABASE_BACKUP_ENABLED`.

Package: `modular_forge.backup`. Dependencies: identity, security.

## Behavior

Manual encrypted SQLite/pg_dump/mysqldump/mariadb-dump/mongodump backups. Restore is an operator workflow: decrypt offline and use the matching database restore utility.

## Owned surface

Tables/collections: backup_jobs and encrypted .mforge files.

Routes: /api/v1/admin/backups and /{id}/download (POST, reauthenticated SUPER_ADMIN only)

## Disable or remove

Extra: database-backup. Remove backup/, registry/toggle/settings/tests/extra. Preserve keys and retained backups; drop only backup_jobs in a new migration. External utilities are not installed by the base Docker image. MySQL/MariaDB additionally require DATABASE_BACKUP_CLIENT_CONFIG pointing to a provisioned owner-only client option file; use verified TLS options matching the selected provider. The application never writes that database password into a new file.

A toggle does not delete database objects or dependency extras. Follow [the modular plan](../MODULAR_PLAN.md), keep old migrations immutable, and run enabled/disabled, boundary and relevant provider contract tests after changes.
