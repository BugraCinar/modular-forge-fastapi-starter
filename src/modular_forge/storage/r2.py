import io
import re
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, UploadFile
from PIL import Image, UnidentifiedImageError

from modular_forge.security.dependencies import current_account, runtime
from modular_forge.shared.errors import ConflictError, DomainError, unavailable

router = APIRouter(prefix="/api/v1/profile/image", tags=["Profile images"])


class R2ImageStorage:
    def __init__(self, settings):
        self.settings = settings
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key,
            aws_secret_access_key=settings.r2_secret_key,
            region_name="auto",
            config=Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 2}),
        )

    def upload(self, owner, content):
        if len(content) > 5 * 1024 * 1024:
            raise DomainError(413, "image_too_large", "Images must not exceed 5 MiB.")
        try:
            with Image.open(io.BytesIO(content)) as image:
                if (
                    image.format not in {"JPEG", "PNG", "WEBP"}
                    or image.width * image.height > 20000000
                ):
                    raise ValueError("Unsupported image")
                image.load()
                converted = image.convert("RGB")
                converted.thumbnail((2048, 2048))
                output = io.BytesIO()
                converted.save(output, "WEBP", quality=85)
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise DomainError(
                422, "invalid_image", "Upload a valid JPEG, PNG or WebP image."
            ) from None
        key = f"{owner}/{uuid4()}.webp"
        try:
            self.client.put_object(
                Bucket=self.settings.r2_bucket_name,
                Key=key,
                Body=output.getvalue(),
                ContentType="image/webp",
                CacheControl="public, max-age=31536000, immutable",
            )
        except (BotoCoreError, ClientError):
            raise unavailable() from None
        return key, self.settings.r2_public_url.rstrip("/") + "/" + key

    def delete(self, owner, key):
        if not re.fullmatch(re.escape(owner) + r"/[0-9a-f-]{36}\.webp", key):
            raise DomainError(400, "invalid_key", "Invalid image key.")
        try:
            self.client.delete_object(Bucket=self.settings.r2_bucket_name, Key=key)
        except (BotoCoreError, ClientError):
            raise unavailable() from None


@router.post("")
def upload_image(file: UploadFile, account=Depends(current_account), rt=Depends(runtime)):
    content = file.file.read(5 * 1024 * 1024 + 1)
    key, url = rt.images.upload(account["id"], content)
    old_key = None
    try:
        with rt.database.transaction() as tx:
            profile = tx.get("profiles", account["id"], lock=True)
            if profile:
                old_key = profile["image_key"]
                if not tx.update(
                    "profiles",
                    profile["id"],
                    {"image_key": key, "image_url": url},
                    revision=profile["revision"],
                ):
                    raise ConflictError()
            else:
                tx.insert(
                    "profiles",
                    {
                        "id": account["id"],
                        "display_name": "",
                        "biography": "",
                        "image_key": key,
                        "image_url": url,
                    },
                )
    except Exception:
        rt.images.delete(account["id"], key)
        raise
    if old_key:
        rt.images.delete(account["id"], old_key)
    return {"url": url}


@router.delete("", status_code=204)
def delete_image(account=Depends(current_account), rt=Depends(runtime)):
    with rt.database.transaction() as tx:
        profile = tx.get("profiles", account["id"], lock=True)
        if profile and profile["image_key"]:
            rt.images.delete(account["id"], profile["image_key"])
            if not tx.update(
                "profiles",
                profile["id"],
                {"image_key": None, "image_url": None},
                revision=profile["revision"],
            ):
                raise ConflictError()


def install(app, runtime):
    runtime.images = R2ImageStorage(runtime.settings)
    app.include_router(router)
