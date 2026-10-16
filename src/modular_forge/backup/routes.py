from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from modular_forge.auth.schemas import PasswordRequest
from modular_forge.security.dependencies import runtime, super_administrator

router = APIRouter(prefix="/api/v1/admin/backups", tags=["Encrypted database backups"])


@router.post("", status_code=201)
def create_backup(data: PasswordRequest, actor=Depends(super_administrator), rt=Depends(runtime)):
    return rt.backups.create(actor, data.password)


@router.post("/{identifier}/download")
def download_backup(
    identifier: str, data: PasswordRequest, actor=Depends(super_administrator), rt=Depends(runtime)
):
    path = rt.backups.download(actor, data.password, identifier)
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)
