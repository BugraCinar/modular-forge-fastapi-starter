import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from modular_forge.modules.catalog import MODULES, table_specs

ROOT = Path(__file__).parents[1]
OPTIONAL = {
    "admin",
    "profile",
    "audit",
    "twofactor",
    "notification",
    "storage",
    "backup",
    "observability",
    "kafka",
    "bootstrap",
}


def test_disabled_modules_expose_no_routes_or_optional_imports(client_factory):
    disabled = {module.toggle: False for module in MODULES if module.toggle}
    with client_factory(**disabled) as (client, rt, _):
        paths = set(client.app.openapi()["paths"])
        for prefix in (
            "/api/v1/profile",
            "/api/v1/admin",
            "/api/v1/two-factor",
            "/docs",
            "/openapi.json",
        ):
            assert not any(path.startswith(prefix) for path in paths)
        result = client.get("/api/v1/modules")
        assert result.status_code == 200 and len(result.json()) == 15
        assert all(not row["enabled"] for row in result.json() if row["kind"] != "required")
        assert {spec.name for spec in rt.database.specs} == {"accounts", "auth_tokens"}


def test_physical_removal_of_optional_packages_still_starts(settings, tmp_path):
    copied = tmp_path / "src"
    shutil.copytree(ROOT / "src", copied, ignore=shutil.ignore_patterns(*OPTIONAL, "__pycache__"))
    values = {**settings.model_dump(), **{m.toggle: False for m in MODULES if m.toggle}}
    script = "\n".join(
        [
            "import json,sys",
            "from fastapi.testclient import TestClient",
            "from modular_forge.shared.config import Settings",
            "from modular_forge.app import create_app",
            f"settings=Settings(_env_file=None, **json.loads({json.dumps(values)!r}))",
            "with TestClient(create_app(settings)) as client:",
            "    assert client.get('/health/ready').status_code == 200",
            "    assert client.get('/api/v1/modules').status_code == 200",
            "assert 'modular_forge.twofactor' not in sys.modules",
        ]
    )
    result = subprocess.run(  # noqa: S603 -- isolated package-removal test with a fixed interpreter
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(copied)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )  # noqa: S603 -- isolated source-removal test, no external input
    assert result.returncode == 0, result.stderr


def test_optional_features_do_not_import_each_others_implementations():
    violations = []
    for source in (ROOT / "src/modular_forge").rglob("*.py"):
        relative = source.relative_to(ROOT / "src/modular_forge")
        owner = relative.parts[0]
        if owner in {"modules", "app.py", "cli.py", "persistence"}:
            continue
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            names = (
                [node.module]
                if isinstance(node, ast.ImportFrom)
                else [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            for name in names:
                parts = (name or "").split(".")
                if (
                    len(parts) > 1
                    and parts[0] == "modular_forge"
                    and parts[1] in OPTIONAL
                    and parts[1] != owner
                ):
                    violations.append(f"{relative}:{node.lineno} imports {name}")
    assert violations == []


def test_catalog_docs_environment_and_schema_snapshot_agree(settings):
    environment = (ROOT / ".env.template").read_text(encoding="utf-8")
    assert environment == (ROOT / "src/modular_forge/env.template").read_text(encoding="utf-8")
    for module in MODULES:
        assert (ROOT / "docs/modules" / (module.id + ".md")).is_file(), module.id
        if module.toggle:
            assert module.toggle.upper() + "=" in environment
    frozen = json.loads(
        (ROOT / "src/modular_forge/persistence/migrations/versions/0001_schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert {x["name"] for x in frozen} == {
        spec.name for spec in table_specs(settings, include_disabled=True)
    }


def test_migrations_then_startup_without_autocreate(settings, tmp_path):
    from fastapi.testclient import TestClient

    from modular_forge.app import create_app
    from modular_forge.cli import migrate
    from modular_forge.shared.config import Settings

    configured = Settings(
        _env_file=None,
        **{
            **settings.model_dump(),
            "database_url": "sqlite:///" + (tmp_path / "migrated.db").as_posix(),
            "auto_create_schema": False,
        },
    )
    migrate(configured)
    migrate(configured)
    with TestClient(create_app(configured)) as client:
        assert client.get("/health/ready").status_code == 200


def test_disabling_two_factor_cannot_bypass_existing_credentials(settings, tmp_path):
    import pytest

    from modular_forge.app import make_database
    from modular_forge.shared.config import Settings

    configured = Settings(
        _env_file=None,
        **{
            **settings.model_dump(),
            "database_url": "sqlite:///" + (tmp_path / "totp.db").as_posix(),
            "module_two_factor_enabled": True,
        },
    )
    database = make_database(configured, table_specs(configured))
    database.initialize(create=True)
    with database.transaction() as tx:
        tx.insert(
            "two_factor_credentials",
            {
                "id": "protected-account",
                "encrypted_secret": "encrypted",
                "enabled": True,
                "pending_until": 0,
                "last_step": -1,
            },
        )
    database.close()
    disabled = Settings(
        _env_file=None, **{**configured.model_dump(), "module_two_factor_enabled": False}
    )
    database = make_database(disabled, table_specs(disabled))
    try:
        with pytest.raises(RuntimeError, match="Active TOTP"):
            database.initialize()
    finally:
        database.close()
