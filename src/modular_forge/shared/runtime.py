from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from modular_forge.auth.service import AuthService
from modular_forge.ratelimit.service import RateLimiter
from modular_forge.security.crypto import Security
from modular_forge.shared.config import Settings
from modular_forge.shared.persistence import Database
from modular_forge.shared.ports import (
    AuditGateway,
    EventGateway,
    NoSecondFactor,
    NotificationGateway,
    NullAudit,
    NullEvents,
    SecondFactorGateway,
    UnavailableNotifications,
)


@dataclass
class Runtime:
    settings: Settings
    database: Database
    security: Security
    rate_limiter: RateLimiter
    notifications: NotificationGateway = field(default_factory=UnavailableNotifications)
    audit: AuditGateway = field(default_factory=NullAudit)
    events: EventGateway = field(default_factory=NullEvents)
    second_factor: SecondFactorGateway = field(default_factory=NoSecondFactor)
    images: Any = None
    backups: Any = None
    closers: list[Callable] = field(default_factory=list)
    starters: list[Callable] = field(default_factory=list)
    auth: AuthService = field(init=False)

    def __post_init__(self):
        self.auth = AuthService(self)
