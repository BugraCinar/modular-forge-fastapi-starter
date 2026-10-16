import base64
from typing import Literal
from urllib.parse import urlsplit

from pydantic import EmailStr, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def secret_bytes(value: str) -> bytes:
    try:
        result = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Secrets must be Base64-encoded random bytes.") from exc
    if len(result) != 32:
        raise ValueError("Secrets must decode to exactly 32 bytes.")
    return result


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", case_sensitive=False, hide_input_in_errors=True
    )

    app_name: str = "Modular Forge FastAPI"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = Field(default="sqlite:///./modularforge.db", repr=False)
    mongodb_database: str = "modularforge"
    auto_create_schema: bool = False
    jwt_secret: str = Field(default="", repr=False)
    pepper: str = Field(default="", repr=False)
    token_hash_secret: str = Field(default="", repr=False)
    jwt_issuer: str = "modular-forge"
    jwt_audience: str = "modular-forge-api"
    access_token_seconds: int = Field(default=900, ge=60, le=3600)
    refresh_token_seconds: int = Field(default=2592000, ge=3600)
    password_min_length: int = Field(default=12, ge=12)
    argon2_memory_cost: int = Field(default=65536, ge=8192)
    argon2_time_cost: int = Field(default=3, ge=1)
    login_max_attempts: int = Field(default=5, ge=1, le=20)
    login_lock_seconds: int = Field(default=900, ge=60)
    cookie_secure: bool = True
    frontend_url: str = "http://localhost:3000"
    cors_allowed_origins: list[str] = ["http://localhost:3000"]
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    max_request_bytes: int = Field(default=6291456, ge=1024, le=16777216)

    rate_limit_backend: Literal["redis", "memory"] = "redis"
    redis_url: str = Field(default="redis://localhost:6379/0", repr=False)
    rate_limit_fail_open: bool = False
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_window: int = Field(default=60, ge=1)

    module_admin_management_enabled: bool = True
    module_user_profile_enabled: bool = True
    module_audit_enabled: bool = True
    module_email_enabled: bool = False
    module_two_factor_enabled: bool = False
    module_image_storage_enabled: bool = False
    module_database_backup_enabled: bool = False
    module_observability_enabled: bool = False
    module_kafka_enabled: bool = False
    module_api_docs_enabled: bool = False
    module_seed_data_enabled: bool = False

    mail_host: str = ""
    mail_port: int = Field(default=587, ge=1, le=65535)
    mail_username: str = ""
    mail_password: str = Field(default="", repr=False)
    mail_sender: EmailStr = "no-reply@example.com"
    mail_starttls: bool = True
    recaptcha_enabled: bool = False
    recaptcha_secret_key: str = Field(default="", repr=False)
    recaptcha_expected_hostname: str = "localhost"
    recaptcha_expected_action: str = "login"
    recaptcha_score_threshold: float = Field(default=0.5, ge=0, le=1)
    two_factor_encryption_key: str = Field(default="", repr=False)
    r2_endpoint_url: str = ""
    r2_access_key: str = Field(default="", repr=False)
    r2_secret_key: str = Field(default="", repr=False)
    r2_bucket_name: str = ""
    r2_public_url: str = ""
    database_backup_encryption_key: str = Field(default="", repr=False)
    database_backup_directory: str = "backups"
    database_backup_max_bytes: int = Field(default=67108864, ge=1024)
    sentry_dsn: str = Field(default="", repr=False)
    kafka_bootstrap_servers: str = ""
    kafka_topic: str = "modular-forge.account-events.v1"
    kafka_security_protocol: Literal["SSL", "SASL_SSL", "PLAINTEXT"] = "SSL"
    kafka_sasl_username: str = ""
    kafka_sasl_password: str = Field(default="", repr=False)
    seed_admin_email: EmailStr = "admin@example.com"
    seed_admin_username: str = "local_admin"
    seed_admin_password: str = Field(default="", repr=False)

    @model_validator(mode="after")
    def validate_security(self):
        keys = [secret_bytes(v) for v in (self.jwt_secret, self.pepper, self.token_hash_secret)]
        if len(set(keys)) != 3:
            raise ValueError("JWT_SECRET, PEPPER and TOKEN_HASH_SECRET must be independent.")
        if "*" in self.cors_allowed_origins or any("*" in x for x in self.cors_allowed_origins):
            raise ValueError("Credentialed CORS requires explicit origins.")
        for origin in [self.frontend_url, *self.cors_allowed_origins]:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Frontend and CORS URLs must be explicit HTTP(S) origins.")
        if self.module_email_enabled and not self.mail_host:
            raise ValueError("MAIL_HOST is required when email is enabled.")
        if self.recaptcha_enabled and not self.recaptcha_secret_key:
            raise ValueError("RECAPTCHA_SECRET_KEY is required.")
        if self.module_two_factor_enabled:
            if secret_bytes(self.two_factor_encryption_key) in keys:
                raise ValueError("Use an independent TOTP encryption key.")
        if self.module_database_backup_enabled:
            if secret_bytes(self.database_backup_encryption_key) in keys:
                raise ValueError("Use an independent backup encryption key.")
        if self.module_image_storage_enabled:
            if not all(
                [
                    self.r2_endpoint_url,
                    self.r2_access_key,
                    self.r2_secret_key,
                    self.r2_bucket_name,
                    self.r2_public_url,
                ]
            ):
                raise ValueError("All R2 settings are required.")
            if not self.module_user_profile_enabled:
                raise ValueError("Image storage requires the user-profile module.")
            if any(
                urlsplit(x).scheme != "https" for x in [self.r2_endpoint_url, self.r2_public_url]
            ):
                raise ValueError("R2 endpoints and public URLs require HTTPS.")
        if self.module_kafka_enabled and not self.kafka_bootstrap_servers:
            raise ValueError("KAFKA_BOOTSTRAP_SERVERS is required.")
        if self.module_observability_enabled and not self.sentry_dsn:
            raise ValueError("SENTRY_DSN is required.")
        if (
            self.module_seed_data_enabled
            and len(self.seed_admin_password) < self.password_min_length
        ):
            raise ValueError("A strong seed administrator password is required.")
        if self.environment == "production":
            if (
                not self.cookie_secure
                or self.rate_limit_fail_open
                or self.rate_limit_backend != "redis"
            ):
                raise ValueError("Production requires Secure cookies and fail-closed Redis limits.")
            if (
                self.auto_create_schema
                or self.module_seed_data_enabled
                or self.module_api_docs_enabled
            ):
                raise ValueError(
                    "Production forbids auto-create, seed accounts and public API docs."
                )
            if (
                "*" in self.allowed_hosts
                or self.argon2_memory_cost < 65536
                or self.argon2_time_cost < 3
            ):
                raise ValueError("Production requires explicit hosts and strong Argon2 parameters.")
            if any(
                urlsplit(x).scheme != "https"
                for x in [self.frontend_url, *self.cors_allowed_origins]
            ):
                raise ValueError("Production frontend/CORS origins require HTTPS.")
            if self.mail_host and not self.mail_starttls:
                raise ValueError("Production SMTP requires STARTTLS.")
            if self.module_kafka_enabled and self.kafka_security_protocol == "PLAINTEXT":
                raise ValueError("Production Kafka requires TLS.")
            if self.database_url.startswith("sqlite:"):
                raise ValueError("SQLite is a local development/test provider.")
            from sqlalchemy.engine import make_url

            database = make_url(self.database_url)
            if (
                database.drivername.startswith("postgresql")
                and database.query.get("sslmode") != "verify-full"
            ):
                raise ValueError("Production PostgreSQL requires sslmode=verify-full.")
            if database.drivername.startswith(("mysql", "mariadb")) and not all(
                str(database.query.get(key, "")).lower() == "true"
                for key in ("ssl_verify_cert", "ssl_verify_identity")
            ):
                raise ValueError(
                    "Production MySQL/MariaDB requires certificate and hostname verification."
                )
            if database.drivername.startswith("mongodb") and not (
                database.drivername == "mongodb+srv"
                or str(database.query.get("tls", "")).lower() == "true"
            ):
                raise ValueError("Production MongoDB requires TLS.")
            if not self.redis_url.startswith("rediss://"):
                raise ValueError("Production Redis requires TLS (rediss://).")
        return self
