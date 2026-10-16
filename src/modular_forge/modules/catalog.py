from dataclasses import dataclass
from importlib import import_module


@dataclass(frozen=True)
class Module:
    id: str
    kind: str
    package: str
    toggle: str | None = None
    dependencies: tuple[str, ...] = ()
    schema: bool = False

    def enabled(self, settings):
        return self.toggle is None or getattr(settings, self.toggle)


MODULES = (
    Module("identity", "required", "identity", schema=True),
    Module(
        "authentication",
        "required",
        "auth",
        dependencies=("identity", "security", "rate-limit"),
        schema=True,
    ),
    Module("security", "required", "security", dependencies=("identity",)),
    Module("rate-limit", "required", "ratelimit"),
    Module("notification-email", "replaceable", "notification", "module_email_enabled"),
    Module(
        "admin-management",
        "optional",
        "admin",
        "module_admin_management_enabled",
        ("identity", "security"),
    ),
    Module(
        "user-profile",
        "optional",
        "profile",
        "module_user_profile_enabled",
        ("identity", "authentication"),
        True,
    ),
    Module("audit", "optional", "audit", "module_audit_enabled", ("identity", "security"), True),
    Module(
        "two-factor",
        "optional",
        "twofactor",
        "module_two_factor_enabled",
        ("identity", "authentication"),
        True,
    ),
    Module(
        "image-storage",
        "replaceable",
        "storage.r2",
        "module_image_storage_enabled",
        ("user-profile",),
    ),
    Module(
        "database-backup",
        "optional",
        "backup",
        "module_database_backup_enabled",
        ("identity", "security"),
        True,
    ),
    Module("observability", "optional", "observability", "module_observability_enabled"),
    Module("api-docs", "optional", "app", "module_api_docs_enabled"),
    Module("kafka", "optional", "kafka", "module_kafka_enabled"),
    Module("seed-data", "optional", "bootstrap", "module_seed_data_enabled", ("identity",)),
)


def table_specs(settings, *, include_disabled=False):
    specs = []
    for module in MODULES:
        if module.schema and (include_disabled or module.enabled(settings)):
            specs.extend(import_module(f"modular_forge.{module.package}.schema").TABLES)
    return specs


def catalog(settings):
    return [
        {
            "id": m.id,
            "kind": m.kind,
            "enabled": m.enabled(settings),
            "package": f"modular_forge.{m.package}",
            "toggle": m.toggle.upper() if m.toggle else None,
            "dependencies": list(m.dependencies),
            "guide": f"docs/modules/{m.id}.md",
        }
        for m in MODULES
    ]


def install_modules(app, runtime):
    for module in MODULES:
        if module.toggle and module.enabled(runtime.settings) and module.id != "api-docs":
            installer = import_module(f"modular_forge.{module.package}").install
            if module.id in {"seed-data", "kafka"}:
                runtime.starters.append(lambda install=installer: install(app, runtime))
            else:
                installer(app, runtime)
