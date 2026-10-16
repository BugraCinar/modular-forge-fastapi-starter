import re
import time
from uuid import uuid4

from modular_forge.shared.errors import ConflictError, DomainError

ROLES = ("USER", "ADMIN", "SUPER_ADMIN")


def normalize_username(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{3,64}", value):
        raise DomainError(
            422, "invalid_username", "Username must contain 3–64 letters, digits or underscores."
        )
    return value


def public_account(account: dict) -> dict:
    return {
        key: account[key]
        for key in ("id", "email", "username", "role", "active", "verified", "created_at")
    }


def create_account(
    tx, email: str, username: str, password_hash: str, *, role="USER", verified=False
):
    email, username = email.strip().lower(), normalize_username(username)
    if tx.one("accounts", email=email) or tx.one("accounts", username=username):
        raise ConflictError()
    return tx.insert(
        "accounts",
        {
            "id": str(uuid4()),
            "email": email,
            "username": username,
            "password_hash": password_hash,
            "role": role,
            "active": True,
            "verified": verified,
            "auth_version": 0,
            "failed_logins": 0,
            "locked_until": 0,
            "created_at": int(time.time()),
            "deactivated_at": None,
        },
    )
