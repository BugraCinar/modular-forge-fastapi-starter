import time

from fastapi import APIRouter, Depends
from pydantic import EmailStr, Field

from modular_forge.auth.schemas import Input, PasswordRequest
from modular_forge.identity.service import public_account
from modular_forge.security.dependencies import current_account, runtime
from modular_forge.shared.errors import ConflictError

router = APIRouter(prefix="/api/v1/profile", tags=["User profile"])


class ProfileUpdate(Input):
    display_name: str = Field(max_length=120)
    biography: str = Field(default="", max_length=2000)


class EmailChange(PasswordRequest):
    email: EmailStr


@router.get("")
def get_profile(account=Depends(current_account), rt=Depends(runtime)):
    with rt.database.transaction() as tx:
        profile = tx.get("profiles", account["id"])
    return {
        **public_account(account),
        "profile": {
            k: v for k, v in (profile or {}).items() if k not in {"revision", "id", "image_key"}
        },
    }


@router.patch("")
def update_profile(data: ProfileUpdate, account=Depends(current_account), rt=Depends(runtime)):
    with rt.database.transaction() as tx:
        profile = tx.get("profiles", account["id"], lock=True)
        if profile:
            if not tx.update(
                "profiles", profile["id"], data.model_dump(), revision=profile["revision"]
            ):
                raise ConflictError()
        else:
            tx.insert(
                "profiles",
                {"id": account["id"], **data.model_dump(), "image_key": None, "image_url": None},
            )
    rt.audit.record("profile.updated", account["id"])
    return data


@router.post("/email", status_code=202)
def change_email(data: EmailChange, account=Depends(current_account), rt=Depends(runtime)):
    rt.auth.change_email(account, data.password, data.email)
    return {"message": "A confirmation email will be sent."}


@router.post("/deactivate", status_code=204)
def deactivate(data: PasswordRequest, account=Depends(current_account), rt=Depends(runtime)):
    with rt.database.transaction() as tx:
        fresh = rt.auth.reauthenticate(tx, account, data.password)
        if fresh["role"] != "USER":
            from modular_forge.shared.errors import DomainError

            raise DomainError(
                403,
                "forbidden",
                "Administrators must be deactivated by another super administrator.",
            )
        if not tx.update(
            "accounts",
            fresh["id"],
            {
                "active": False,
                "auth_version": fresh["auth_version"] + 1,
                "deactivated_at": int(time.time()),
            },
            revision=fresh["revision"],
        ):
            raise ConflictError()
    rt.audit.record("account.deactivated", account["id"])
