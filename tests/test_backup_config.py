import os
from types import SimpleNamespace

import pytest

from modular_forge.backup.service import BackupService
from modular_forge.shared.config import Settings


def test_mysql_backup_uses_managed_config_without_copying_credentials(
    settings, tmp_path, monkeypatch
):
    configuration = tmp_path / "managed.cnf"
    configuration.write_text("[client]\nhost=localhost\nuser=backup\n", encoding="utf-8")
    configuration.chmod(0o600)
    configured = Settings(
        _env_file=None,
        **{
            **settings.model_dump(),
            "database_url": "mysql+pymysql://forge:runtime-only-password@localhost/db",
            "database_backup_client_config": str(configuration),
            "database_backup_directory": str(tmp_path / "encrypted"),
        },
    )
    service = BackupService(SimpleNamespace(settings=configured))
    commands = []

    def execute(command, **options):
        commands.append(command)
        options["stdout"].write(b"a database dump")

    monkeypatch.setattr("modular_forge.backup.service.subprocess.run", execute)
    service._dump(tmp_path / "dump", str(tmp_path))
    assert "--defaults-extra-file=" + str(configuration.resolve()) in commands[0]
    assert "runtime-only-password" not in " ".join(commands[0])
    assert not (tmp_path / "client.cnf").exists()


@pytest.mark.skipif(
    os.name != "posix", reason="POSIX mode check; Windows requires a provisioned private ACL"
)
def test_mysql_backup_rejects_world_readable_managed_config(settings, tmp_path):
    configuration = tmp_path / "public.cnf"
    configuration.write_text("[client]\n", encoding="utf-8")
    configuration.chmod(0o644)
    configured = Settings(
        _env_file=None,
        **{
            **settings.model_dump(),
            "database_url": "mysql+pymysql://localhost/db",
            "database_backup_client_config": str(configuration),
            "database_backup_directory": str(tmp_path / "encrypted"),
        },
    )
    with pytest.raises(ValueError, match="owner-only"):
        BackupService(SimpleNamespace(settings=configured))
