import base64
import hmac
import os
import time

import pyotp
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from modular_forge.shared.config import secret_bytes
from modular_forge.shared.errors import ConflictError, DomainError, unauthorized


class TOTPService:
    def __init__(self, runtime):
        self.rt = runtime
        self.cipher = AESGCM(secret_bytes(runtime.settings.two_factor_encryption_key))

    def encrypt(self, secret, account_id):
        nonce = os.urandom(12)
        return base64.b64encode(
            nonce + self.cipher.encrypt(nonce, secret.encode(), account_id.encode())
        ).decode()

    def decrypt(self, value, account_id):
        raw = base64.b64decode(value)
        return self.cipher.decrypt(raw[:12], raw[12:], account_id.encode()).decode()

    def _step(self, credential, code):
        if len(code) != 6 or not code.isdigit():
            return None
        secret = self.decrypt(credential["encrypted_secret"], credential["id"])
        step = int(time.time()) // 30
        for offset in (0, -1, 1):
            candidate = step + offset
            if candidate > credential["last_step"] and hmac.compare_digest(
                pyotp.TOTP(secret).at(candidate * 30), code
            ):
                return candidate
        return None

    def required(self, account_id):
        with self.rt.database.transaction() as tx:
            credential = tx.get("two_factor_credentials", account_id)
        return bool(credential and credential["enabled"])

    def setup(self, principal, password):
        secret = pyotp.random_base32()
        with self.rt.database.transaction() as tx:
            account = self.rt.auth.reauthenticate(tx, principal, password)
            existing = tx.get("two_factor_credentials", account["id"], lock=True)
            if existing and existing["enabled"]:
                raise DomainError(
                    409, "two_factor_enabled", "Disable the current credential before replacing it."
                )
            changes = {
                "encrypted_secret": self.encrypt(secret, account["id"]),
                "enabled": False,
                "pending_until": int(time.time()) + 600,
                "last_step": -1,
            }
            if existing:
                if not tx.update(
                    "two_factor_credentials", account["id"], changes, revision=existing["revision"]
                ):
                    raise ConflictError()
            else:
                tx.insert("two_factor_credentials", {"id": account["id"], **changes})
        return {
            "secret": secret,
            "provisioning_uri": pyotp.TOTP(secret).provisioning_uri(
                name=account["email"], issuer_name=self.rt.settings.app_name
            ),
        }

    def enable(self, principal, password, code):
        with self.rt.database.transaction() as tx:
            account = self.rt.auth.reauthenticate(tx, principal, password)
            credential = tx.get("two_factor_credentials", account["id"], lock=True)
            if (
                not credential
                or credential["enabled"]
                or credential["pending_until"] <= int(time.time())
            ):
                raise unauthorized()
            step = self._step(credential, code)
            if step is None:
                raise unauthorized()
            if not tx.update(
                "two_factor_credentials",
                account["id"],
                {"enabled": True, "last_step": step, "pending_until": 0},
                revision=credential["revision"],
            ):
                raise ConflictError()
            if not tx.update(
                "accounts",
                account["id"],
                {"auth_version": account["auth_version"] + 1},
                revision=account["revision"],
            ):
                raise ConflictError()
        self.rt.audit.record("two_factor.enabled", account["id"])

    def disable(self, principal, password, code):
        with self.rt.database.transaction() as tx:
            account = self.rt.auth.reauthenticate(tx, principal, password)
            credential = tx.get("two_factor_credentials", account["id"], lock=True)
            if not credential or not credential["enabled"] or self._step(credential, code) is None:
                raise unauthorized()
            from modular_forge.shared.persistence import eq

            tx.delete("two_factor_credentials", eq(id=account["id"]))
            if not tx.update(
                "accounts",
                account["id"],
                {"auth_version": account["auth_version"] + 1},
                revision=account["revision"],
            ):
                raise ConflictError()
        self.rt.audit.record("two_factor.disabled", account["id"])

    def challenge(self, account_id, auth_version):
        raw = self.rt.security.opaque_token()
        with self.rt.database.transaction() as tx:
            tx.insert(
                "two_factor_challenges",
                {
                    "id": self.rt.security.token_hash(raw, purpose="2fa"),
                    "account_id": account_id,
                    "auth_version": auth_version,
                    "attempts": 0,
                    "used": False,
                    "expires_at": int(time.time()) + 300,
                },
            )
        return raw

    def consume(self, challenge, code):
        invalid = False
        with self.rt.database.transaction() as tx:
            token = tx.get(
                "two_factor_challenges",
                self.rt.security.token_hash(challenge, purpose="2fa"),
                lock=True,
            )
            if (
                not token
                or token["used"]
                or token["expires_at"] <= int(time.time())
                or token["attempts"] >= 5
            ):
                raise unauthorized()
            account = tx.get("accounts", token["account_id"], lock=True)
            credential = tx.get("two_factor_credentials", token["account_id"], lock=True)
            if (
                not account
                or not account["active"]
                or account["auth_version"] != token["auth_version"]
                or not credential
                or not credential["enabled"]
            ):
                raise unauthorized()
            step = self._step(credential, code)
            attempts = token["attempts"] + 1
            if not tx.update(
                "two_factor_challenges",
                token["id"],
                {"attempts": attempts, "used": step is not None or attempts >= 5},
                revision=token["revision"],
            ):
                raise unauthorized()
            if step is None:
                invalid = True
            elif not tx.update(
                "two_factor_credentials",
                credential["id"],
                {"last_step": step},
                revision=credential["revision"],
            ):
                raise unauthorized()
        if invalid:
            raise unauthorized()
        return account["id"], token["auth_version"]
