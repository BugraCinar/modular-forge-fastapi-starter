import time

import jwt
from conftest import PASSWORD, authorization, login

from modular_forge.shared.config import secret_bytes


def test_register_verify_login_and_only_hashes_persist(client, app, mailbox):
    data = {"email": "new@example.com", "username": "new_user", "password": PASSWORD}
    assert client.post("/api/v1/auth/register", json=data).status_code == 202
    assert "token" not in client.post("/api/v1/auth/register", json=data).text
    assert login(client, "new_user").status_code == 401
    token = mailbox.token()
    with app.state.runtime.database.transaction() as tx:
        account = tx.one("accounts", username="new_user")
        records = tx.find("auth_tokens")
    assert PASSWORD not in str(account) and account["password_hash"].startswith("$argon2id$")
    assert token not in str(records)
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 401
    assert login(client, "new_user").status_code == 200


def test_rotation_and_reuse_revoke_all_sessions(client, account_factory):
    account_factory()
    session = login(client).json()
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]})
    assert rotated.status_code == 200
    latest = rotated.json()
    assert latest["refresh_token"] != session["refresh_token"]
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": latest["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/profile", headers={"Authorization": "Bearer " + latest["access_token"]}
        ).status_code
        == 401
    )


def test_cookie_refresh_and_logout_require_signed_csrf(client, account_factory):
    account_factory()
    response = login(client, use_cookie=True)
    assert response.status_code == 200
    assert response.json()["refresh_token"] is None
    cookies = response.headers.get_list("set-cookie")
    assert any("HttpOnly" in x and "Secure" in x and "__Host-forge_refresh" in x for x in cookies)
    assert client.post("/api/v1/auth/refresh").status_code == 403
    csrf = client.cookies["__Host-forge_csrf"]
    assert (
        client.post(
            "/api/v1/auth/refresh", headers={"X-XSRF-TOKEN": csrf, "Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    refreshed = client.post("/api/v1/auth/refresh", headers={"X-XSRF-TOKEN": csrf})
    assert refreshed.status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert (
        client.post(
            "/api/v1/auth/logout", headers={"X-XSRF-TOKEN": client.cookies["__Host-forge_csrf"]}
        ).status_code
        == 204
    )
    assert "__Host-forge_refresh" not in client.cookies


def test_reset_invalidates_access_refresh_and_other_reset_tokens(client, account_factory, mailbox):
    account = account_factory()
    session = login(client).json()
    assert (
        client.post("/api/v1/auth/forgot-password", json={"email": account["email"]}).status_code
        == 202
    )
    token = mailbox.token()
    result = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "password": "A-new-strong-password!99"}
    )
    assert result.status_code == 200
    assert (
        client.post(
            "/api/v1/auth/reset-password", json={"token": token, "password": PASSWORD}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/profile", headers={"Authorization": "Bearer " + session["access_token"]}
        ).status_code
        == 401
    )


def test_password_change_requires_old_password_and_revokes_access(client, account_factory):
    account_factory()
    headers = authorization(client)
    assert (
        client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={"password": "wrong", "new_password": PASSWORD},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={"password": PASSWORD, "new_password": "Another-strong-password!"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/profile", headers=headers).status_code == 401


def test_account_lockout_persists(client, account_factory, app):
    account = account_factory()
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/auth/login", json={"username": account["username"], "password": "wrong"}
            ).status_code
            == 401
        )
    with app.state.runtime.database.transaction() as tx:
        stored = tx.get("accounts", account["id"])
    assert stored["failed_logins"] == 5 and stored["locked_until"] > int(time.time())
    assert login(client).status_code == 429


def test_jwt_wrong_algorithm_issuer_and_expiry_rejected(client, account_factory, app):
    account_factory()
    rt = app.state.runtime
    valid = login(client).json()["access_token"]
    claims = jwt.decode(valid, options={"verify_signature": False})
    for changes in (
        {"iss": "someone-else"},
        {"exp": 1},
        {"aud": "wrong"},
        {"type": "refresh"},
        {"ver": 123},
    ):
        token = jwt.encode(
            {**claims, **changes}, secret_bytes(rt.settings.jwt_secret), algorithm="HS256"
        )
        assert (
            client.get("/api/v1/profile", headers={"Authorization": "Bearer " + token}).status_code
            == 401
        )
    unsigned = jwt.encode(claims, key="", algorithm="none")
    assert (
        client.get("/api/v1/profile", headers={"Authorization": "Bearer " + unsigned}).status_code
        == 401
    )


def test_session_revocation_is_owner_scoped(client, account_factory):
    account_factory()
    account_factory("other_user")
    headers = authorization(client)
    sessions = client.get("/api/v1/auth/sessions", headers=headers).json()
    other = authorization(client, "other_user")
    identifier = sessions[0]["id"]
    assert client.delete("/api/v1/auth/sessions/" + identifier, headers=other).status_code == 404
    assert client.delete("/api/v1/auth/sessions/" + identifier, headers=headers).status_code == 204


def test_input_errors_never_echo_password_or_token(client):
    password = "never-echo-this-password"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "bad", "username": "u", "password": password, "extra": "sensitive"},
    )
    assert response.status_code == 422
    assert password not in response.text and "sensitive" not in response.text
