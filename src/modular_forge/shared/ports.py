from typing import Any, Protocol


class NotificationGateway(Protocol):
    def send(self, recipient: str, subject: str, text: str) -> None: ...


class AuditGateway(Protocol):
    def record(self, event: str, actor_id: str | None, target_id: str | None = None) -> None: ...


class EventGateway(Protocol):
    def publish(self, event: dict[str, Any]) -> None: ...


class SecondFactorGateway(Protocol):
    def required(self, account_id: str) -> bool: ...
    def challenge(self, account_id: str, auth_version: int) -> str: ...
    def consume(self, challenge: str, code: str) -> tuple[str, int]: ...


class ImageStorage(Protocol):
    def upload(self, owner: str, content: bytes) -> tuple[str, str]: ...
    def delete(self, owner: str, key: str) -> None: ...


class UnavailableNotifications:
    def send(self, recipient: str, subject: str, text: str) -> None:
        from modular_forge.shared.errors import unavailable

        raise unavailable()


class NullAudit:
    def record(self, event: str, actor_id: str | None, target_id: str | None = None) -> None:
        pass


class NullEvents:
    def publish(self, event: dict[str, Any]) -> None:
        pass


class NoSecondFactor:
    def required(self, account_id: str) -> bool:
        return False

    def challenge(self, account_id: str, auth_version: int) -> str:
        raise RuntimeError("No second-factor provider is installed.")

    def consume(self, challenge: str, code: str) -> tuple[str, int]:
        from modular_forge.shared.errors import unauthorized

        raise unauthorized()
