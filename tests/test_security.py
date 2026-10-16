import base64

import fakeredis
import pytest
from pydantic import ValidationError
from redis.exceptions import ConnectionError as RedisConnectionError

from modular_forge.ratelimit.service import RateLimiter, RedisStore
from modular_forge.security.crypto import Security
from modular_forge.shared.config import Settings
from modular_forge.shared.errors import DomainError


def test_invalid_secrets_and_wildcard_cors_rejected(settings):
    for changes in (
        {"jwt_secret": ""},
        {"jwt_secret": settings.pepper},
        {"pepper": base64.b64encode(b"short").decode()},
        {"cors_allowed_origins": ["*"]},
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **{**settings.model_dump(), **changes})
    assert settings.jwt_secret not in repr(settings) and settings.database_url not in repr(settings)


def test_password_hashes_require_the_original_pepper(settings):
    from conftest import PASSWORD

    first = Security(settings)
    encoded = first.hash_password(PASSWORD)
    changed = Settings(
        _env_file=None, **{**settings.model_dump(), "pepper": base64.b64encode(b"z" * 32).decode()}
    )
    assert first.verify_password(PASSWORD, encoded)
    assert not Security(changed).verify_password(PASSWORD, encoded)
    assert not first.verify_password(PASSWORD + "wrong", encoded)
    assert encoded.startswith("$argon2id$")


@pytest.mark.parametrize(
    "unsafe",
    [
        {"cookie_secure": False},
        {"rate_limit_backend": "memory"},
        {"rate_limit_fail_open": True},
        {"module_api_docs_enabled": True},
        {"auto_create_schema": True},
        {"allowed_hosts": ["*"]},
        {"frontend_url": "http://site.example"},
        {"database_url": "postgresql+psycopg://localhost/db"},
        {"redis_url": "redis://localhost:6379"},
    ],
)
def test_production_rejects_unsafe_configuration(settings, unsafe):
    valid = {
        **settings.model_dump(),
        "environment": "production",
        "database_url": "postgresql+psycopg://db.example/forge?sslmode=verify-full",
        "auto_create_schema": False,
        "rate_limit_backend": "redis",
        "redis_url": "rediss://redis.example:6379",
        "argon2_memory_cost": 65536,
        "argon2_time_cost": 3,
        "frontend_url": "https://site.example",
        "cors_allowed_origins": ["https://site.example"],
        "allowed_hosts": ["api.example"],
    }
    Settings(_env_file=None, **valid)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**valid, **unsafe})


def test_headers_and_health_details(client):
    response = client.get("/health/ready")
    assert response.status_code == 200 and response.json() == {"status": "up"}
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]


def test_cors_and_untrusted_host(client):
    response = client.options(
        "/api/v1/auth/login",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers
    allowed = client.options(
        "/api/v1/auth/login",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert client.get("/health/live", headers={"Host": "evil.example"}).status_code == 400


def test_global_limit_ignores_spoofed_forwarded_ip(client_factory):
    with client_factory(rate_limit_requests=2) as (client, _, _):
        assert client.get("/api/v1/modules").status_code == 200
        assert (
            client.get("/api/v1/modules", headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 200
        )
        limited = client.get("/api/v1/modules", headers={"X-Forwarded-For": "5.6.7.8"})
        assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
        assert client.get("/health/live").status_code == 200


def test_redis_lua_expiry_and_fail_closed(settings):
    store = RedisStore(settings.redis_url)
    store.client = fakeredis.FakeRedis()
    store.script = store.client.register_script(
        __import__("modular_forge.ratelimit.service", fromlist=["SCRIPT"]).SCRIPT
    )
    security = Security(settings)
    limiter = RateLimiter(settings, security, store)
    limiter.check("test", "private@example.com", 1, 60)
    with pytest.raises(DomainError) as exc:
        limiter.check("test", "private@example.com", 1, 60)
    assert exc.value.status == 429
    keys = store.client.keys("*")
    assert b"private@example.com" not in keys[0] and store.client.ttl(keys[0]) > 0

    class BrokenStore:
        def hit(self, key, window):
            raise RedisConnectionError()

    with pytest.raises(DomainError) as exc:
        RateLimiter(settings, security, BrokenStore()).check("x", "y", 1, 1)
    assert exc.value.status == 503


def test_oversized_request_rejected_before_parsing(client_factory):
    with client_factory(max_request_bytes=1024) as (client, _, _):
        assert client.post("/api/v1/auth/login", content=b"x" * 2048).status_code == 413


def test_server_error_does_not_disclose_exception(client, app, monkeypatch):
    secret = "never-disclose-a-database-password"

    def fail(*a):
        raise RuntimeError(secret)

    monkeypatch.setattr(app.state.runtime.auth, "login", fail)
    response = client.post("/api/v1/auth/login", json={"username": "any", "password": "any"})
    assert response.status_code == 500 and secret not in response.text


def test_captcha_checks_action_hostname_and_score(settings, monkeypatch):
    import httpx

    from modular_forge.auth.captcha import verify_captcha

    configured = Settings(
        _env_file=None,
        **{
            **settings.model_dump(),
            "recaptcha_enabled": True,
            "recaptcha_secret_key": "test-captcha-key",
        },
    )
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: httpx.Response(
            200,
            request=httpx.Request("POST", "https://www.google.com"),
            json={"success": True, "hostname": "evil.example", "action": "login", "score": 0.9},
        ),
    )
    with pytest.raises(DomainError):
        verify_captcha(configured, "response")
