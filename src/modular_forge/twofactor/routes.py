from fastapi import APIRouter, Depends
from pydantic import Field

from modular_forge.auth.schemas import PasswordRequest
from modular_forge.security.dependencies import current_account, runtime

router = APIRouter(prefix="/api/v1/two-factor", tags=["Two-factor authentication"])


class TOTPRequest(PasswordRequest):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


@router.post("/setup")
def setup(data: PasswordRequest, account=Depends(current_account), rt=Depends(runtime)):
    return rt.second_factor.setup(account, data.password)


@router.post("/enable")
def enable(data: TOTPRequest, account=Depends(current_account), rt=Depends(runtime)):
    rt.second_factor.enable(account, data.password, data.code)
    return {"message": "Two-factor authentication enabled. Sign in again using a fresh code."}


@router.post("/disable")
def disable(data: TOTPRequest, account=Depends(current_account), rt=Depends(runtime)):
    rt.second_factor.disable(account, data.password, data.code)
    return {"message": "Two-factor authentication disabled. Sign in again."}
