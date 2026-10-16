import json
import os
import subprocess
import tempfile
import time
from contextlib import closing
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.engine import make_url

from modular_forge.shared.config import secret_bytes
from modular_forge.shared.errors import DomainError, unavailable

MAGIC = b"MFORGE1"


class BackupService:
    def __init__(self, runtime):
        self.rt = runtime
        self.key = secret_bytes(runtime.settings.database_backup_encryption_key)
        self.directory = Path(runtime.settings.database_backup_directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.client_config = None
        if runtime.settings.database_url.startswith(("mysql", "mariadb")):
            self.client_config = Path(runtime.settings.database_backup_client_config).resolve(
                strict=True
            )
            if not self.client_config.is_file() or (
                os.name == "posix" and self.client_config.stat().st_mode & 0o077
            ):
                raise ValueError(
                    "The backup client configuration must be a private, owner-only file."
                )

    def encrypt(self, content):
        nonce = os.urandom(12)
        return MAGIC + nonce + AESGCM(self.key).encrypt(nonce, content, MAGIC)

    def decrypt(self, content):
        if not content.startswith(MAGIC):
            raise ValueError("Invalid backup format")
        return AESGCM(self.key).decrypt(content[7:19], content[19:], MAGIC)

    def _dump(self, output, temporary):
        url = make_url(self.rt.settings.database_url)
        if url.drivername.startswith("sqlite"):
            import sqlite3

            with (
                self.rt.database.engine.connect() as connection,
                closing(sqlite3.connect(output)) as destination,
            ):
                connection.connection.driver_connection.backup(destination)
            return
        environment = os.environ.copy()
        if url.drivername.startswith("postgresql"):
            environment.update(
                PGHOST=url.host or "localhost",
                PGPORT=str(url.port or 5432),
                PGDATABASE=url.database or "",
                PGUSER=url.username or "",
                PGPASSWORD=url.password or "",
                PGSSLMODE=str(url.query.get("sslmode", "prefer")),
            )
            if url.query.get("sslrootcert"):
                environment["PGSSLROOTCERT"] = str(url.query["sslrootcert"])
            command = ["pg_dump", "--format=custom", "--no-owner"]
        elif url.drivername.startswith(("mysql", "mariadb")):
            binary = "mariadb-dump" if url.drivername.startswith("mariadb") else "mysqldump"
            command = [
                binary,
                f"--defaults-extra-file={self.client_config}",
                "--single-transaction",
                "--skip-lock-tables",
                "--",
                url.database or "",
            ]
        elif url.drivername.startswith("mongodb"):
            config = Path(temporary) / "mongo.yml"
            config.write_text(
                "uri: " + json.dumps(self.rt.settings.database_url) + "\n", encoding="utf-8"
            )
            config.chmod(0o600)
            command = [
                "mongodump",
                f"--config={config}",
                f"--db={self.rt.settings.mongodb_database}",
                "--archive",
            ]
        else:
            raise DomainError(
                422, "unsupported_provider", "This provider does not support backups."
            )
        with Path(output).open("wb") as stream:
            subprocess.run(  # noqa: S603 -- fixed server-owned dump tools, never request input
                command,
                env=environment,
                stdout=stream,
                stderr=subprocess.DEVNULL,
                timeout=120,
                check=True,
                shell=False,
            )  # noqa: S603 -- fixed tools and server-owned configuration, never request input

    def create(self, principal, password):
        self.rt.rate_limiter.check("backup", principal["id"], 2, 3600)
        identifier = str(uuid4())
        file_name = identifier + ".mforge"
        with self.rt.database.transaction() as tx:
            self.rt.auth.reauthenticate(tx, principal, password)
            tx.insert(
                "backup_jobs",
                {
                    "id": identifier,
                    "file_name": file_name,
                    "created_by": principal["id"],
                    "created_at": int(time.time()),
                    "status": "running",
                },
            )
        try:
            with tempfile.TemporaryDirectory(prefix="modular-forge-backup-") as temporary:
                output = Path(temporary) / "dump"
                self._dump(output, temporary)
                if output.stat().st_size > self.rt.settings.database_backup_max_bytes:
                    raise DomainError(
                        413, "backup_too_large", "Backup exceeds the configured size limit."
                    )
                encrypted = self.encrypt(output.read_bytes())
            destination = self.directory / file_name
            with destination.open("xb") as stream:
                stream.write(encrypted)
            destination.chmod(0o600)
            with self.rt.database.transaction() as tx:
                job = tx.get("backup_jobs", identifier)
                tx.update(
                    "backup_jobs", identifier, {"status": "complete"}, revision=job["revision"]
                )
        except Exception:
            with self.rt.database.transaction() as tx:
                job = tx.get("backup_jobs", identifier)
                tx.update("backup_jobs", identifier, {"status": "failed"}, revision=job["revision"])
            raise unavailable() from None
        self.rt.audit.record("backup.created", principal["id"], identifier)
        return {"id": identifier, "status": "complete"}

    def download(self, principal, password, identifier):
        with self.rt.database.transaction() as tx:
            self.rt.auth.reauthenticate(tx, principal, password)
            job = tx.get("backup_jobs", identifier)
        if not job or job["status"] != "complete":
            raise DomainError(404, "not_found", "Backup not found.")
        try:
            safe_name = str(UUID(identifier)) + ".mforge"
        except ValueError:
            raise DomainError(404, "not_found", "Backup not found.") from None
        path = (self.directory / safe_name).resolve()
        if path.parent != self.directory or not path.is_file():
            raise DomainError(404, "not_found", "Backup not found.")
        self.rt.audit.record("backup.downloaded", principal["id"], identifier)
        return path
