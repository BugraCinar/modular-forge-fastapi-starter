import argparse
import base64
import getpass
import os
import secrets
from pathlib import Path


def initialize_env(path):
    template = Path(__file__).parent / "env.template"
    text = template.read_text(encoding="utf-8")
    for name in (
        "JWT_SECRET",
        "PEPPER",
        "TOKEN_HASH_SECRET",
        "TWO_FACTOR_ENCRYPTION_KEY",
        "DATABASE_BACKUP_ENCRYPTION_KEY",
    ):
        text = text.replace(
            name + "=\n", name + "=" + base64.b64encode(os.urandom(32)).decode() + "\n"
        )
    text = text.replace("DB_PASSWORD=\n", "DB_PASSWORD=" + secrets.token_urlsafe(32) + "\n")
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(text)
    Path(path).chmod(0o600)
    print(f"Created {path}. Keep it out of version control.")


def migrate(settings):
    from modular_forge.app import make_database
    from modular_forge.modules.catalog import table_specs

    specs = table_specs(settings, include_disabled=True)
    database = make_database(settings, specs)
    try:
        if settings.database_url.startswith(("mongodb://", "mongodb+srv://")):
            database.initialize(create=True)
        else:
            from alembic import command
            from alembic.config import Config

            config = Config()
            config.set_main_option(
                "script_location", str(Path(__file__).parent / "persistence" / "migrations")
            )
            with database.engine.begin() as connection:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
    finally:
        database.close()
    print("Database migrations applied.")


def main():
    parser = argparse.ArgumentParser(description="Modular Forge management commands")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser(
        "init-env", help="Create a local .env with independent random secrets"
    )
    init.add_argument("--path", default=".env")
    commands.add_parser("migrate", help="Apply SQL migrations or initialize MongoDB indexes")
    admin = commands.add_parser("create-admin", help="Create a verified super administrator")
    admin.add_argument("--email", required=True)
    admin.add_argument("--username", required=True)
    commands.add_parser("cleanup", help="Remove expired tokens and audit events older than 30 days")
    args = parser.parse_args()
    if args.command == "init-env":
        initialize_env(args.path)
        return
    from modular_forge.shared.config import Settings

    settings = Settings()
    if args.command == "migrate":
        migrate(settings)
        return
    from modular_forge.app import make_database
    from modular_forge.modules.catalog import table_specs

    database = make_database(settings, table_specs(settings))
    try:
        database.initialize()
        if args.command == "create-admin":
            from pydantic import EmailStr, TypeAdapter

            from modular_forge.identity.service import create_account
            from modular_forge.security.crypto import Security

            password = getpass.getpass("Administrator password: ")
            if password != getpass.getpass("Confirm password: "):
                parser.error("Passwords do not match.")
            email = str(TypeAdapter(EmailStr).validate_python(args.email))
            encoded = Security(settings).hash_password(password)
            with database.transaction() as tx:
                create_account(tx, email, args.username, encoded, role="SUPER_ADMIN", verified=True)
            print("Administrator created.")
        elif args.command == "cleanup":
            import time

            now = int(time.time())
            with database.transaction() as tx:
                tx.delete("auth_tokens", [("expires_at", "lt", now)])
                if settings.module_audit_enabled:
                    tx.delete("audit_events", [("created_at", "lt", now - 30 * 86400)])
                if settings.module_two_factor_enabled:
                    tx.delete("two_factor_challenges", [("expires_at", "lt", now)])
            print("Expired records removed.")
    finally:
        database.close()
