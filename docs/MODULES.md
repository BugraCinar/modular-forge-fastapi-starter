# Module catalog

Live discovery: `GET /api/v1/modules`. Core defaults below are distinct from explicit development overrides in `.env.template`.

| Id | Kind | Default | Dependencies | Guide |
|---|---|---|---|---|
| identity | required | on | none | [identity](modules/identity.md) |
| authentication | required | on | identity, security, rate-limit | [authentication](modules/authentication.md) |
| security | required | on | identity | [security](modules/security.md) |
| rate-limit | required | on | none | [rate-limit](modules/rate-limit.md) |
| notification-email | replaceable | off | none | [notification-email](modules/notification-email.md) |
| admin-management | optional | on | identity, security | [admin-management](modules/admin-management.md) |
| user-profile | optional | on | identity, authentication | [user-profile](modules/user-profile.md) |
| audit | optional | on | identity, security | [audit](modules/audit.md) |
| two-factor | optional | off | identity, authentication | [two-factor](modules/two-factor.md) |
| image-storage | replaceable | off | user-profile | [image-storage](modules/image-storage.md) |
| database-backup | optional | off | identity, security | [database-backup](modules/database-backup.md) |
| observability | optional | off | none | [observability](modules/observability.md) |
| api-docs | optional | off | none | [api-docs](modules/api-docs.md) |
| kafka | optional | off | none | [kafka](modules/kafka.md) |
| seed-data | optional | off | identity | [seed-data](modules/seed-data.md) |

See [architecture](ARCHITECTURE.md), [add/remove rules](MODULAR_PLAN.md), [database providers](DATABASES.md) and [security](SECURITY.md).
