import base64
from contextlib import contextmanager
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from modular_forge.app import create_app
from modular_forge.identity.service import create_account
from modular_forge.shared.config import Settings

PASSWORD = "A-long-test-password!42"


class Mailbox:
    def __init__(self):
        self.messages = []

    def send(self, recipient, subject, text):
        self.messages.append((recipient, subject, text))

    def token(self):
        url = self.messages[-1][2].splitlines()[1]
        return parse_qs(urlsplit(url).query)["token"][0]


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        environment="test",
        database_url="sqlite:///:memory:",
        auto_create_schema=True,
        rate_limit_backend="memory",
        rate_limit_requests=10000,
        jwt_secret=base64.b64encode(b"a" * 32).decode(),
        pepper=base64.b64encode(b"b" * 32).decode(),
        token_hash_secret=base64.b64encode(b"c" * 32).decode(),
        two_factor_encryption_key=base64.b64encode(b"d" * 32).decode(),
        database_backup_encryption_key=base64.b64encode(b"e" * 32).decode(),
        argon2_memory_cost=8192,
        argon2_time_cost=1,
    )


@pytest.fixture
def mailbox():
    return Mailbox()


@pytest.fixture
def app(settings, mailbox):
    return create_app(settings, notifications=mailbox)


@pytest.fixture
def client(app):
    with TestClient(app, base_url="https://testserver") as client:
        yield client


@pytest.fixture
def client_factory(settings):
    @contextmanager
    def factory(**changes):
        mailbox = Mailbox()
        configured = Settings(_env_file=None, **{**settings.model_dump(), **changes})
        app = create_app(configured, notifications=mailbox)
        with TestClient(app, base_url="https://testserver") as client:
            yield client, app.state.runtime, mailbox

    return factory


@pytest.fixture
def account_factory(app, client):
    def factory(username="sample_user", *, role="USER", verified=True):
        rt = app.state.runtime
        with rt.database.transaction() as tx:
            return create_account(
                tx,
                username + "@example.com",
                username,
                rt.security.hash_password(PASSWORD),
                role=role,
                verified=verified,
            )

    return factory


def login(client, username="sample_user", **extra):
    return client.post(
        "/api/v1/auth/login", json={"username": username, "password": PASSWORD, **extra}
    )


def authorization(client, username="sample_user"):
    result = login(client, username)
    assert result.status_code == 200, result.text
    return {"Authorization": "Bearer " + result.json()["access_token"]}
