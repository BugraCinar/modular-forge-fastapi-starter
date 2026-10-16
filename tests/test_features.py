import time
from types import SimpleNamespace

import pyotp
from conftest import PASSWORD, authorization, login

from modular_forge.identity.service import create_account


def test_profile_changes_email_confirmation_and_deactivation(client, account_factory, mailbox, app):
    account_factory()
    headers = authorization(client)
    assert (
        client.patch(
            "/api/v1/profile",
            headers=headers,
            json={"display_name": "Example", "biography": "A short biography"},
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/profile", headers=headers).json()["profile"]["display_name"]
        == "Example"
    )
    assert (
        client.post(
            "/api/v1/profile/email",
            headers=headers,
            json={"email": "new-address@example.com", "password": PASSWORD},
        ).status_code
        == 202
    )
    token = mailbox.token()
    assert (
        client.post("/api/v1/auth/confirm-email-change", json={"token": token}).status_code == 200
    )
    assert client.get("/api/v1/profile", headers=headers).status_code == 401
    headers = authorization(client)
    assert (
        client.post(
            "/api/v1/profile/deactivate", headers=headers, json={"password": PASSWORD}
        ).status_code
        == 204
    )
    assert client.get("/api/v1/profile", headers=headers).status_code == 401
    assert login(client).status_code == 401


def test_admin_roles_and_password_reset(client, account_factory):
    user = account_factory()
    admin = account_factory("an_admin", role="ADMIN")
    account_factory("root_admin", role="SUPER_ADMIN")
    user_headers = authorization(client)
    admin_headers = authorization(client, "an_admin")
    root_headers = authorization(client, "root_admin")
    assert client.get("/api/v1/admin/users", headers=user_headers).status_code == 403
    visible = client.get("/api/v1/admin/users", headers=admin_headers).json()["items"]
    assert all(row["role"] == "USER" and "password_hash" not in row for row in visible)
    assert (
        client.patch(
            "/api/v1/admin/users/" + user["id"],
            headers=admin_headers,
            json={"password": PASSWORD, "role": "SUPER_ADMIN"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/admin/users/" + admin["id"],
            headers=admin_headers,
            json={"password": PASSWORD, "active": False},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/admin/users/" + user["id"],
            headers=root_headers,
            json={"password": PASSWORD, "role": "ADMIN"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/profile", headers=user_headers).status_code == 401
    assert (
        client.post(
            "/api/v1/admin/users/" + user["id"] + "/password",
            headers=root_headers,
            json={"password": PASSWORD, "new_password": "Reset-from-admin-password!"},
        ).status_code
        == 204
    )


def test_audit_records_actions_without_credentials(client, account_factory, app):
    account_factory("root_admin", role="SUPER_ADMIN")
    headers = authorization(client, "root_admin")
    events = client.get("/api/v1/admin/audit", headers=headers)
    assert events.status_code == 200
    assert any(item["event"] == "authentication.login" for item in events.json()["items"])
    assert (
        PASSWORD not in events.text
        and "password_hash" not in events.text
        and "access_token" not in events.text
    )


def test_email_change_events_publish_only_after_commit(client, app, account_factory, mailbox):
    class Events:
        def __init__(self):
            self.values = []

        def publish(self, value):
            self.values.append(value)

    sink = Events()
    app.state.runtime.events = sink
    account = account_factory()
    headers = authorization(client)
    client.post(
        "/api/v1/profile/email",
        headers=headers,
        json={"password": PASSWORD, "email": "changed@example.com"},
    )
    token = mailbox.token()
    assert sink.values == []
    assert (
        client.post("/api/v1/auth/confirm-email-change", json={"token": token}).status_code == 200
    )
    assert (
        sink.values[0]["account_id"] == account["id"]
        and sink.values[0]["data"]["email"] == "changed@example.com"
    )
    assert (
        client.post("/api/v1/auth/confirm-email-change", json={"token": token}).status_code == 401
    )
    assert len(sink.values) == 1


def test_totp_lifecycle_replay_and_attempt_limit(client_factory, monkeypatch):
    with client_factory(module_two_factor_enabled=True) as (client, rt, _):
        with rt.database.transaction() as tx:
            account = create_account(
                tx,
                "totp@example.com",
                "totp_user",
                rt.security.hash_password(PASSWORD),
                verified=True,
            )
        headers = authorization(client, "totp_user")
        setup = client.post(
            "/api/v1/two-factor/setup", headers=headers, json={"password": PASSWORD}
        )
        assert setup.status_code == 200
        secret = setup.json()["secret"]
        with rt.database.transaction() as tx:
            credential = tx.get("two_factor_credentials", account["id"])
        assert secret not in str(credential)
        now = int(time.time())
        assert (
            client.post(
                "/api/v1/two-factor/enable",
                headers=headers,
                json={"password": PASSWORD, "code": pyotp.TOTP(secret).at(now)},
            ).status_code
            == 200
        )
        assert client.get("/api/v1/profile", headers=headers).status_code == 401
        challenge = login(client, "totp_user").json()["challenge"]
        # The enrollment code is already consumed and cannot authenticate a login.
        assert (
            client.post(
                "/api/v1/auth/two-factor",
                json={"challenge": challenge, "code": pyotp.TOTP(secret).at(now)},
            ).status_code
            == 401
        )
        later = (now // 30 + 1) * 30
        monkeypatch.setattr(
            "modular_forge.twofactor.service.time", SimpleNamespace(time=lambda: later)
        )
        verified = client.post(
            "/api/v1/auth/two-factor",
            json={"challenge": challenge, "code": pyotp.TOTP(secret).at(later)},
        )
        assert verified.status_code == 200
        assert (
            client.post(
                "/api/v1/auth/two-factor",
                json={"challenge": challenge, "code": pyotp.TOTP(secret).at(later)},
            ).status_code
            == 401
        )
        headers = {"Authorization": "Bearer " + verified.json()["access_token"]}
        monkeypatch.setattr(
            "modular_forge.twofactor.service.time", SimpleNamespace(time=lambda: later + 30)
        )
        assert (
            client.post(
                "/api/v1/two-factor/disable",
                headers=headers,
                json={"password": PASSWORD, "code": pyotp.TOTP(secret).at(later + 30)},
            ).status_code
            == 200
        )
        assert client.get("/api/v1/profile", headers=headers).status_code == 401


def test_totp_wrong_codes_exhaust_challenge(client_factory):
    with client_factory(module_two_factor_enabled=True) as (_, rt, _):
        with rt.database.transaction() as tx:
            account = create_account(
                tx,
                "attempts@example.com",
                "attempts",
                rt.security.hash_password(PASSWORD),
                verified=True,
            )
            tx.insert(
                "two_factor_credentials",
                {
                    "id": account["id"],
                    "encrypted_secret": rt.second_factor.encrypt(
                        pyotp.random_base32(), account["id"]
                    ),
                    "enabled": True,
                    "pending_until": 0,
                    "last_step": -1,
                },
            )
        challenge = rt.second_factor.challenge(account["id"], account["auth_version"])
        import pytest

        from modular_forge.shared.errors import DomainError

        for _ in range(6):
            with pytest.raises(DomainError):
                rt.second_factor.consume(challenge, "invalid")
        with rt.database.transaction() as tx:
            record = tx.get(
                "two_factor_challenges", rt.security.token_hash(challenge, purpose="2fa")
            )
        assert record["attempts"] == 5 and record["used"]


def test_encrypted_sqlite_backup_download_and_tamper_detection(client_factory, tmp_path):
    import pytest
    from cryptography.exceptions import InvalidTag

    with client_factory(
        module_database_backup_enabled=True, database_backup_directory=str(tmp_path)
    ) as (client, rt, _):
        with rt.database.transaction() as tx:
            create_account(
                tx,
                "backup@example.com",
                "backup_admin",
                rt.security.hash_password(PASSWORD),
                role="SUPER_ADMIN",
                verified=True,
            )
        headers = authorization(client, "backup_admin")
        result = client.post("/api/v1/admin/backups", headers=headers, json={"password": PASSWORD})
        assert result.status_code == 201, result.text
        identifier = result.json()["id"]
        download = client.post(
            f"/api/v1/admin/backups/{identifier}/download",
            headers=headers,
            json={"password": PASSWORD},
        )
        assert download.status_code == 200
        encrypted = download.content
        assert encrypted.startswith(b"MFORGE1") and b"SQLite format" not in encrypted
        assert rt.backups.decrypt(encrypted).startswith(b"SQLite format 3")
        corrupted = encrypted[:-1] + bytes([encrypted[-1] ^ 1])
        with pytest.raises(InvalidTag):
            rt.backups.decrypt(corrupted)


def test_r2_reencodes_images_and_rejects_non_images(settings, monkeypatch):
    import io

    from PIL import Image

    from modular_forge.storage.r2 import R2ImageStorage

    class S3:
        def put_object(self, **values):
            self.values = values

        def delete_object(self, **values):
            self.deleted = values

    client = S3()
    monkeypatch.setattr("modular_forge.storage.r2.boto3.client", lambda *a, **k: client)
    storage = R2ImageStorage(settings)
    source = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(source, "PNG")
    key, url = storage.upload("an-owner", source.getvalue())
    assert key.startswith("an-owner/") and key.endswith(".webp")
    assert client.values["ContentType"] == "image/webp"
    assert Image.open(io.BytesIO(client.values["Body"])).format == "WEBP"
    import pytest

    from modular_forge.shared.errors import DomainError

    with pytest.raises(DomainError):
        storage.upload("an-owner", b"<svg onload=alert(1)>")
    with pytest.raises(DomainError):
        storage.delete("other-owner", key)
