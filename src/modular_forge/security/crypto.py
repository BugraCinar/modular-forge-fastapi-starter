import base64
import hashlib
import hmac
import secrets
import time
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

from modular_forge.shared.config import secret_bytes
from modular_forge.shared.errors import DomainError, unauthorized


class Security:
    def __init__(self, settings):
        self.settings = settings
        self.pepper = secret_bytes(settings.pepper)
        self.token_key = secret_bytes(settings.token_hash_secret)
        self.jwt_key = secret_bytes(settings.jwt_secret)
        self.hasher = PasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_cost,
            parallelism=4,
            type=Type.ID,
        )
        self.dummy_hash = self.hash_password(secrets.token_urlsafe(32))

    def _peppered(self, password: str):
        return base64.b64encode(hmac.digest(self.pepper, password.encode(), "sha256")).decode()

    def hash_password(self, password: str):
        if len(password) < self.settings.password_min_length or len(password) > 1024:
            raise DomainError(
                422,
                "weak_password",
                f"Password must contain {self.settings.password_min_length}–1024 characters.",
            )
        return self.hasher.hash(self._peppered(password))

    def verify_password(self, password: str, encoded: str):
        if len(password) > 1024:
            return False
        try:
            return self.hasher.verify(encoded, self._peppered(password))
        except (VerificationError, InvalidHashError):
            return False

    def token_hash(self, raw: str, *, purpose="token") -> str:
        return hmac.new(self.token_key, (purpose + ":" + raw).encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def opaque_token():
        return secrets.token_urlsafe(48)

    def access_token(self, account: dict):
        now = int(time.time())
        return jwt.encode(
            {
                "sub": account["id"],
                "role": account["role"],
                "ver": account["auth_version"],
                "iss": self.settings.jwt_issuer,
                "aud": self.settings.jwt_audience,
                "type": "access",
                "iat": now,
                "exp": now + self.settings.access_token_seconds,
                "jti": str(uuid4()),
            },
            self.jwt_key,
            algorithm="HS256",
        )

    def decode_access(self, token: str):
        try:
            value = jwt.decode(
                token,
                self.jwt_key,
                algorithms=["HS256"],
                issuer=self.settings.jwt_issuer,
                audience=self.settings.jwt_audience,
                options={
                    "require": ["sub", "role", "ver", "iss", "aud", "type", "iat", "exp", "jti"]
                },
            )
            if value["type"] != "access":
                raise unauthorized()
            return value
        except jwt.PyJWTError:
            raise unauthorized() from None
