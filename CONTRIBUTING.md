# Contributing

Start with [the modular plan](docs/MODULAR_PLAN.md) and the affected
[module guide](docs/modules/). A change should have one clear purpose and leave
unrelated modules alone. Required security behavior and released migrations
must remain intact.

## Development environment

From the repository root, run `uv sync --frozen --all-extras`. Create a private
local environment with `uv run --no-sync modular-forge init-env` when running
the app; tests inject their own configuration. See [Windows setup](docs/WINDOWS.md)
and [test selection](docs/TESTING.md).

Run the verification commands listed in [README](README.md#verify) before a pull
request. Dependency changes need a committed `uv.lock` update and a fresh audit.
Database changes need a new forward migration, with retention and rollback notes;
do not edit the released initial migration or schema snapshot.

## Changes to modules

Keep a feature's routes, DTOs, service and schema in its own package. Cross-module
calls use shared ports. A new optional feature needs a toggle, catalog entry,
removal guide, enabled/disabled tests and synchronized environment templates.
Optional SDKs must not load when their feature is disabled.

Explain the trigger, resulting behavior and validation in the pull request.
Describe API/configuration changes so a consumer can assess upgrade impact.
For documentation-only changes, check commands and local links; new runtime
tests are unnecessary when behavior is unchanged.

## Reporting issues

Use synthetic account/data examples and a minimal reproduction. Include the
commit/version, Python version, database provider and affected module. Keep
passwords, `.env`, database URLs and tokens out of issues or logs. Report suspected
vulnerabilities privately as described in [the security guide](docs/SECURITY.md).
