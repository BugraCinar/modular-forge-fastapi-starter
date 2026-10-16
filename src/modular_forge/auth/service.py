import time
from urllib.parse import urlencode
from uuid import uuid4

from modular_forge.auth.captcha import verify_captcha
from modular_forge.identity.service import create_account, normalize_username
from modular_forge.shared.errors import ConflictError, DomainError, unauthorized
from modular_forge.shared.persistence import eq


class AuthService:
    def __init__(self, runtime):
        self.rt = runtime

    def issue_token(self, tx, account, kind, ttl, *, family=None, context=None):
        raw = self.rt.security.opaque_token()
        tx.insert(
            "auth_tokens",
            {
                "id": self.rt.security.token_hash(raw, purpose=kind),
                "account_id": account["id"],
                "kind": kind,
                "family": family or str(uuid4()),
                "used": False,
                "expires_at": int(time.time()) + ttl,
                "created_at": int(time.time()),
                "auth_version": account["auth_version"],
                "context": context or {},
            },
        )
        return raw

    def session(self, tx, account, *, family=None):
        raw = self.issue_token(
            tx, account, "refresh", self.rt.settings.refresh_token_seconds, family=family
        )
        return {
            "access_token": self.rt.security.access_token(account),
            "refresh_token": raw,
            "token_type": "bearer",
            "expires_in": self.rt.settings.access_token_seconds,
        }

    def _mail(self, tx, account, kind, route, subject, *, context=None):
        raw = self.issue_token(tx, account, kind, 3600, context=context)
        url = self.rt.settings.frontend_url.rstrip("/") + route + "?" + urlencode({"token": raw})
        recipient = (context or {}).get("email", account["email"])
        tx.after_commit(
            lambda: self.rt.notifications.send(
                recipient,
                subject,
                f"Open this link to continue:\n{url}\n\nIf you did not request this, ignore this message.",
            )
        )

    def register(self, data):
        verify_captcha(self.rt.settings, data.captcha)
        encoded = self.rt.security.hash_password(data.password)
        username = normalize_username(data.username)
        try:
            with self.rt.database.transaction() as tx:
                if tx.one("accounts", email=str(data.email).lower()) or tx.one(
                    "accounts", username=username
                ):
                    return
                account = create_account(tx, str(data.email), username, encoded)
                self._mail(tx, account, "verify", "/verify-email", "Verify your email")
        except ConflictError:
            return

    def login(self, data):
        verify_captcha(self.rt.settings, data.captcha)
        identity = data.username.strip().lower()
        self.rt.rate_limiter.check(
            "login-account",
            identity,
            self.rt.settings.login_max_attempts,
            self.rt.settings.login_lock_seconds,
        )
        invalid = False
        account = None
        with self.rt.database.transaction() as tx:
            found = tx.one(
                "accounts", **({"email": identity} if "@" in identity else {"username": identity})
            )
            account = tx.get("accounts", found["id"], lock=True) if found else None
            valid_password = self.rt.security.verify_password(
                data.password, account["password_hash"] if account else self.rt.security.dummy_hash
            )
            if (
                not account
                or not account["active"]
                or not account["verified"]
                or account["locked_until"] > int(time.time())
            ):
                invalid = True
            elif not valid_password:
                failures = account["failed_logins"] + 1
                changes = {"failed_logins": failures}
                if failures >= self.rt.settings.login_max_attempts:
                    changes["locked_until"] = int(time.time()) + self.rt.settings.login_lock_seconds
                    changes["auth_version"] = account["auth_version"] + 1
                if not tx.update("accounts", account["id"], changes, revision=account["revision"]):
                    raise ConflictError()
                invalid = True
            else:
                if not tx.update(
                    "accounts",
                    account["id"],
                    {"failed_logins": 0, "locked_until": 0},
                    revision=account["revision"],
                ):
                    raise ConflictError()
                account = tx.get("accounts", account["id"])
        if invalid or account is None:
            self.rt.audit.record("authentication.failed", account["id"] if account else None)
            raise unauthorized()
        if self.rt.second_factor.required(account["id"]):
            return {
                "second_factor_required": True,
                "challenge": self.rt.second_factor.challenge(
                    account["id"], account["auth_version"]
                ),
            }
        with self.rt.database.transaction() as tx:
            fresh = tx.get("accounts", account["id"], lock=True)
            if not fresh or fresh["auth_version"] != account["auth_version"] or not fresh["active"]:
                raise unauthorized()
            result = self.session(tx, fresh)
        self.rt.audit.record("authentication.login", account["id"])
        return result

    def complete_two_factor(self, challenge, code):
        account_id, version = self.rt.second_factor.consume(challenge, code)
        with self.rt.database.transaction() as tx:
            account = tx.get("accounts", account_id, lock=True)
            if (
                not account
                or not account["active"]
                or not account["verified"]
                or account["auth_version"] != version
            ):
                raise unauthorized()
            result = self.session(tx, account)
        self.rt.audit.record("authentication.login_2fa", account_id)
        return result

    def refresh(self, raw):
        reused = False
        with self.rt.database.transaction() as tx:
            token = tx.get(
                "auth_tokens", self.rt.security.token_hash(raw, purpose="refresh"), lock=True
            )
            if not token or token["kind"] != "refresh" or token["expires_at"] <= int(time.time()):
                raise unauthorized()
            account = tx.get("accounts", token["account_id"], lock=True)
            if (
                not account
                or not account["active"]
                or not account["verified"]
                or token["auth_version"] != account["auth_version"]
            ):
                raise unauthorized()
            if token["used"]:
                tx.update(
                    "accounts",
                    account["id"],
                    {"auth_version": account["auth_version"] + 1},
                    revision=account["revision"],
                )
                reused = True
            else:
                if not tx.update(
                    "auth_tokens", token["id"], {"used": True}, revision=token["revision"]
                ):
                    raise unauthorized()
                result = self.session(tx, account, family=token["family"])
        if reused:
            self.rt.audit.record("authentication.refresh_reuse", account["id"])
            raise unauthorized()
        return result

    def logout(self, raw):
        with self.rt.database.transaction() as tx:
            token = tx.get(
                "auth_tokens", self.rt.security.token_hash(raw, purpose="refresh"), lock=True
            )
            if token:
                # Deleting a family invalidates its latest token, including after rotation.
                tx.delete("auth_tokens", eq(family=token["family"], kind="refresh"))

    def consume_token(self, tx, raw, kind):
        token = tx.get("auth_tokens", self.rt.security.token_hash(raw, purpose=kind), lock=True)
        if (
            not token
            or token["used"]
            or token["kind"] != kind
            or token["expires_at"] <= int(time.time())
        ):
            raise unauthorized()
        account = tx.get("accounts", token["account_id"], lock=True)
        if not account or not account["active"] or account["auth_version"] != token["auth_version"]:
            raise unauthorized()
        if not tx.update("auth_tokens", token["id"], {"used": True}, revision=token["revision"]):
            raise unauthorized()
        return token, account

    def verify_email(self, raw):
        with self.rt.database.transaction() as tx:
            _, account = self.consume_token(tx, raw, "verify")
            if not tx.update(
                "accounts", account["id"], {"verified": True}, revision=account["revision"]
            ):
                raise ConflictError()
        self.rt.audit.record("account.verified", account["id"])

    def request_email(self, email, kind):
        email = str(email).lower()
        self.rt.rate_limiter.check("email-" + kind, email, 3, 3600)
        with self.rt.database.transaction() as tx:
            account = tx.one("accounts", email=email)
            if not account or not account["active"]:
                return
            if kind == "reset" and account["verified"]:
                self._mail(tx, account, "reset", "/reset-password", "Reset your password")
            elif kind == "verify" and not account["verified"]:
                self._mail(tx, account, "verify", "/verify-email", "Verify your email")

    def reset_password(self, raw, new_password):
        encoded = self.rt.security.hash_password(new_password)
        with self.rt.database.transaction() as tx:
            _, account = self.consume_token(tx, raw, "reset")
            if not tx.update(
                "accounts",
                account["id"],
                {
                    "password_hash": encoded,
                    "auth_version": account["auth_version"] + 1,
                    "failed_logins": 0,
                    "locked_until": 0,
                },
                revision=account["revision"],
            ):
                raise ConflictError()
        self.rt.audit.record("account.password_reset", account["id"])

    def change_password(self, principal, password, new_password):
        encoded = self.rt.security.hash_password(new_password)
        with self.rt.database.transaction() as tx:
            account = self.reauthenticate(tx, principal, password)
            if not tx.update(
                "accounts",
                account["id"],
                {"password_hash": encoded, "auth_version": account["auth_version"] + 1},
                revision=account["revision"],
            ):
                raise ConflictError()
        self.rt.audit.record("account.password_changed", account["id"])

    def reauthenticate(self, tx, principal, password):
        self.rt.rate_limiter.check("reauthentication", principal["id"], 10, 900)
        account = tx.get("accounts", principal["id"], lock=True)
        if (
            not account
            or not account["active"]
            or account["auth_version"] != principal["auth_version"]
            or not self.rt.security.verify_password(password, account["password_hash"])
        ):
            raise unauthorized()
        return account

    def sessions(self, principal):
        with self.rt.database.transaction() as tx:
            rows = tx.find(
                "auth_tokens",
                eq(
                    account_id=principal["id"],
                    kind="refresh",
                    used=False,
                    auth_version=principal["auth_version"],
                )
                + [("expires_at", "gt", int(time.time()))],
                limit=100,
            )
        return [
            {"id": r["id"], "created_at": r["created_at"], "expires_at": r["expires_at"]}
            for r in rows
        ]

    def revoke_session(self, principal, identifier):
        with self.rt.database.transaction() as tx:
            token = tx.get("auth_tokens", identifier)
            if not token or token["account_id"] != principal["id"] or token["kind"] != "refresh":
                raise DomainError(404, "not_found", "Session not found.")
            tx.delete("auth_tokens", eq(family=token["family"], account_id=principal["id"]))

    def change_email(self, principal, password, email):
        email = str(email).lower()
        with self.rt.database.transaction() as tx:
            account = self.reauthenticate(tx, principal, password)
            if tx.one("accounts", email=email):
                raise ConflictError()
            self._mail(
                tx,
                account,
                "email-change",
                "/confirm-email-change",
                "Confirm your new email",
                context={"email": email},
            )

    def confirm_email_change(self, raw):
        with self.rt.database.transaction() as tx:
            token, account = self.consume_token(tx, raw, "email-change")
            email = token["context"]["email"]
            if not tx.update(
                "accounts",
                account["id"],
                {"email": email, "auth_version": account["auth_version"] + 1},
                revision=account["revision"],
            ):
                raise ConflictError()
            event = {
                "id": str(uuid4()),
                "type": "account.email_changed",
                "version": 1,
                "occurred_at": int(time.time()),
                "account_id": account["id"],
                "data": {"email": email},
            }
            tx.after_commit(lambda: self.rt.events.publish(event))
        self.rt.audit.record("account.email_changed", account["id"])
