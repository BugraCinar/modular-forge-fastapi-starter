from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import EmailStr, Field

from modular_forge.auth.schemas import PasswordRequest
from modular_forge.identity.service import create_account, public_account
from modular_forge.security.dependencies import administrator, runtime
from modular_forge.shared.errors import ConflictError, DomainError

router = APIRouter(prefix="/api/v1/admin", tags=["Administration"])


class CreateAccount(PasswordRequest):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64)
    account_password: str = Field(min_length=12, max_length=1024)
    role: Literal["USER", "ADMIN", "SUPER_ADMIN"] = "USER"


class UpdateAccount(PasswordRequest):
    active: bool | None = None
    role: Literal["USER", "ADMIN", "SUPER_ADMIN"] | None = None


class ResetAccountPassword(PasswordRequest):
    new_password: str = Field(min_length=12, max_length=1024)


def authorize_target(actor, target, new_role=None):
    if actor["id"] == target["id"]:
        raise DomainError(403, "forbidden", "Use self-service endpoints for your own account.")
    if actor["role"] != "SUPER_ADMIN" and (
        target["role"] != "USER" or new_role not in {None, "USER"}
    ):
        raise DomainError(403, "forbidden", "Only super administrators may manage administrators.")


@router.get("/users")
def list_accounts(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    actor=Depends(administrator),
    rt=Depends(runtime),
):
    from modular_forge.shared.persistence import eq

    conditions = eq(role="USER") if actor["role"] != "SUPER_ADMIN" else []
    with rt.database.transaction() as tx:
        rows = tx.find(
            "accounts",
            conditions,
            limit=limit,
            offset=offset,
            order_by="created_at",
            descending=True,
        )
        total = tx.count("accounts", conditions)
    return {
        "items": [public_account(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/users", status_code=201)
def create_user(data: CreateAccount, actor=Depends(administrator), rt=Depends(runtime)):
    if actor["role"] != "SUPER_ADMIN" and data.role != "USER":
        raise DomainError(403, "forbidden", "Only super administrators may create administrators.")
    encoded = rt.security.hash_password(data.account_password)
    with rt.database.transaction() as tx:
        rt.auth.reauthenticate(tx, actor, data.password)
        account = create_account(tx, str(data.email), data.username, encoded, role=data.role)
        rt.auth._mail(tx, account, "verify", "/verify-email", "Verify your account")
    rt.audit.record("admin.account_created", actor["id"], account["id"])
    return public_account(account)


@router.patch("/users/{identifier}")
def update_user(
    identifier: str, data: UpdateAccount, actor=Depends(administrator), rt=Depends(runtime)
):
    with rt.database.transaction() as tx:
        fresh_actor = rt.auth.reauthenticate(tx, actor, data.password)
        target = tx.get("accounts", identifier, lock=True)
        if not target:
            raise DomainError(404, "not_found", "Account not found.")
        authorize_target(fresh_actor, target, data.role)
        changes = data.model_dump(exclude_none=True, exclude={"password"})
        if changes:
            changes["auth_version"] = target["auth_version"] + 1
            if not tx.update("accounts", identifier, changes, revision=target["revision"]):
                raise ConflictError()
        result = tx.get("accounts", identifier)
    rt.audit.record("admin.account_updated", actor["id"], identifier)
    return public_account(result)


@router.post("/users/{identifier}/password", status_code=204)
def reset_user_password(
    identifier: str, data: ResetAccountPassword, actor=Depends(administrator), rt=Depends(runtime)
):
    encoded = rt.security.hash_password(data.new_password)
    with rt.database.transaction() as tx:
        fresh_actor = rt.auth.reauthenticate(tx, actor, data.password)
        target = tx.get("accounts", identifier, lock=True)
        if not target:
            raise DomainError(404, "not_found", "Account not found.")
        authorize_target(fresh_actor, target)
        if not tx.update(
            "accounts",
            identifier,
            {"password_hash": encoded, "auth_version": target["auth_version"] + 1},
            revision=target["revision"],
        ):
            raise ConflictError()
    rt.audit.record("admin.password_reset", actor["id"], identifier)
