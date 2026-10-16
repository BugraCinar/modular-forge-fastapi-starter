from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from modular_forge.shared.errors import DomainError, unauthorized

bearer = HTTPBearer(auto_error=False)


def runtime(request: Request):
    return request.app.state.runtime


def current_account(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)
):
    if not credentials:
        raise unauthorized()
    rt = runtime(request)
    claims = rt.security.decode_access(credentials.credentials)
    with rt.database.transaction() as tx:
        account = tx.get("accounts", claims["sub"])
    if (
        not account
        or not account["active"]
        or not account["verified"]
        or account["auth_version"] != claims["ver"]
        or account["role"] != claims["role"]
    ):
        raise unauthorized()
    return account


def administrator(account=Depends(current_account)):
    if account["role"] not in {"ADMIN", "SUPER_ADMIN"}:
        raise DomainError(403, "forbidden", "Administrator access is required.")
    return account


def super_administrator(account=Depends(administrator)):
    if account["role"] != "SUPER_ADMIN":
        raise DomainError(403, "forbidden", "Super administrator access is required.")
    return account
