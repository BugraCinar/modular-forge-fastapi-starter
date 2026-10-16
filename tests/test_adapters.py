import json
from types import SimpleNamespace

import pytest

from modular_forge.shared.errors import DomainError


def test_smtp_uses_verified_starttls_before_credentials(settings, monkeypatch):
    from modular_forge.notification.service import SMTPNotifications
    from modular_forge.shared.config import Settings

    configured = Settings(
        _env_file=None,
        **{
            **settings.model_dump(),
            "mail_host": "smtp.example.com",
            "mail_username": "mailer",
            "mail_password": "mail-secret",
        },
    )
    operations = []

    class SMTP:
        def __init__(self, host, port, timeout):
            operations.append("connect")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            operations.append("close")

        def ehlo(self):
            operations.append("ehlo")

        def starttls(self, context):
            import ssl

            assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
            operations.append("tls")

        def login(self, username, password):
            assert operations[-2:] == ["tls", "ehlo"]
            operations.append("login")

        def send_message(self, message):
            assert "mail-secret" not in str(message)
            operations.append("send")

    monkeypatch.setattr("modular_forge.notification.service.smtplib.SMTP", SMTP)
    SMTPNotifications(configured).send(
        "recipient@example.com", "Verification", "A verification link"
    )
    assert operations == ["connect", "ehlo", "tls", "ehlo", "login", "send", "close"]


def test_smtp_failure_is_generic(settings, monkeypatch):
    from modular_forge.notification.service import SMTPNotifications

    def fail(*args, **kwargs):
        raise OSError("credential-that-must-not-escape")

    monkeypatch.setattr("modular_forge.notification.service.smtplib.SMTP", fail)
    with pytest.raises(DomainError) as error:
        SMTPNotifications(settings).send("recipient@example.com", "Subject", "Text")
    assert error.value.status == 503 and "credential" not in error.value.message


def test_kafka_lifecycle_and_event_publication(client_factory, monkeypatch):
    import modular_forge.kafka.service

    sent = []
    closed = []

    class Producer:
        def __init__(self, **options):
            assert options["acks"] == "all" and options["security_protocol"] == "SSL"

        def send(self, topic, key, value):
            sent.append((topic, key, value))
            return SimpleNamespace(get=lambda timeout: None)

        def close(self, timeout):
            closed.append(True)

    monkeypatch.setattr(modular_forge.kafka.service, "KafkaProducer", Producer)
    event = {
        "id": "an-event",
        "account_id": "an-account",
        "type": "account.email_changed",
        "data": {"email": "verified@example.com"},
    }
    with client_factory(
        module_kafka_enabled=True, kafka_bootstrap_servers="broker.example:9093"
    ) as (_, rt, _):
        rt.events.publish(event)
        assert sent[0][1] == event["account_id"] and sent[0][2] == event
    assert closed == [True]


def test_observability_scrubs_request_user_and_exception_details():
    from modular_forge.observability import scrub_event

    event = {
        "request": {"data": {"password": "hidden-password"}},
        "user": {"email": "private@example.com"},
        "breadcrumbs": ["hidden-token"],
        "exception": {"values": [{"value": "database-secret", "type": "RuntimeError"}]},
    }
    scrubbed = json.dumps(scrub_event(event, {}))
    assert all(
        value not in scrubbed
        for value in ["hidden-password", "private@example.com", "hidden-token", "database-secret"]
    )
    assert "RuntimeError" in scrubbed


def test_seed_accounts_are_opt_in_and_password_is_not_overwritten(client_factory):
    from conftest import PASSWORD, login

    from modular_forge.bootstrap import install

    with client_factory(module_seed_data_enabled=True, seed_admin_password=PASSWORD) as (
        client,
        rt,
        _,
    ):
        assert login(client, "local_admin").status_code == 200
        with rt.database.transaction() as tx:
            original = tx.one("accounts", username="local_admin")
        install(client.app, rt)
        with rt.database.transaction() as tx:
            retained = tx.one("accounts", username="local_admin")
        assert (
            retained["password_hash"] == original["password_hash"]
            and retained["role"] == "SUPER_ADMIN"
        )
