# image-storage

Kind: **replaceable**. Default: **off**. Setting: `MODULE_IMAGE_STORAGE_ENABLED`.

Package: `modular_forge.storage.r2`. Dependencies: user-profile.

## Behavior

Owner-scoped Cloudflare R2 uploads/deletion; image type/pixel/size validation and WebP re-encoding.

## Owned surface

Tables/collections: image fields on consumer-owned profiles; no independent table.

Routes: /api/v1/profile/image

## Disable or remove

Extra: image-storage. Remove storage/r2.py, its R2 settings/toggle/registry/tests/extra. Keep ImageStorage if another adapter is installed. Export/delete bucket objects under the application policy; do not drop profiles.

A toggle does not delete database objects or dependency extras. Follow [the modular plan](../MODULAR_PLAN.md), keep old migrations immutable, and run enabled/disabled, boundary and relevant provider contract tests after changes.
