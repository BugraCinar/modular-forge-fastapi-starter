import logging
from uuid import uuid4

from anyio import to_thread
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

from modular_forge.shared.errors import DomainError

logger = logging.getLogger(__name__)


class SecurityMiddleware:
    def __init__(self, app, runtime):
        self.app, self.rt = app, runtime

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        received = 0
        started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > self.rt.settings.max_request_bytes:
                raise DomainError(413, "request_too_large", "Request exceeds the size limit.")
            return message

        async def secure_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                headers["Cache-Control"] = "no-store"
                headers["Content-Security-Policy"] = (
                    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
                )
                if self.rt.settings.module_api_docs_enabled and scope["path"] in {
                    "/docs",
                    "/redoc",
                }:
                    headers["Content-Security-Policy"] = (
                        "default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; connect-src 'self'; frame-ancestors 'none'"
                    )
                if self.rt.settings.environment == "production":
                    headers["Strict-Transport-Security"] = "max-age=31536000"
            await send(message)

        try:
            length = Headers(scope=scope).get("content-length")
            if length:
                try:
                    size = int(length)
                except ValueError:
                    raise DomainError(400, "invalid_length", "Invalid Content-Length.") from None
                if size < 0:
                    raise DomainError(400, "invalid_length", "Invalid Content-Length.")
                if size > self.rt.settings.max_request_bytes:
                    raise DomainError(413, "request_too_large", "Request exceeds the size limit.")
            if scope["path"] not in {"/health/live", "/health/ready"}:
                identity = str((scope.get("client") or ("unknown", 0))[0])
                await to_thread.run_sync(
                    self.rt.rate_limiter.check,
                    "global",
                    identity,
                    self.rt.settings.rate_limit_requests,
                    self.rt.settings.rate_limit_window,
                )
            await self.app(scope, limited_receive, secure_send)
        except DomainError as error:
            if started:
                raise
            headers = (
                {"Retry-After": str(error.retry_after)} if error.retry_after is not None else None
            )
            await JSONResponse(
                {"error": {"code": error.code, "message": error.message}, "request_id": request_id},
                status_code=error.status,
                headers=headers,
            )(scope, receive, secure_send)
        except Exception as error:
            if started:
                raise
            logger.error(
                "Unhandled request error; request_id=%s type=%s", request_id, type(error).__name__
            )
            await JSONResponse(
                {
                    "error": {"code": "internal_error", "message": "An unexpected error occurred."},
                    "request_id": request_id,
                },
                status_code=500,
            )(scope, receive, secure_send)
