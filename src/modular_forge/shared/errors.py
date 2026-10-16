class DomainError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.retry_after: int | None = None


class ConflictError(DomainError):
    def __init__(self):
        super().__init__(409, "conflict", "The resource changed or already exists.")


def unauthorized() -> DomainError:
    return DomainError(401, "unauthorized", "Invalid credentials or expired session.")


def unavailable() -> DomainError:
    return DomainError(503, "service_unavailable", "A required service is unavailable.")
