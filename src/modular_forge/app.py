from contextlib import asynccontextmanager

from anyio import to_thread
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from modular_forge import __version__
from modular_forge.auth.routes import router as auth_router
from modular_forge.modules.catalog import catalog, install_modules, table_specs
from modular_forge.ratelimit.service import RateLimiter
from modular_forge.security.crypto import Security
from modular_forge.security.middleware import SecurityMiddleware
from modular_forge.shared.config import Settings
from modular_forge.shared.errors import DomainError
from modular_forge.shared.runtime import Runtime


def make_database(settings, specs):
    if settings.database_url.startswith(("mongodb://", "mongodb+srv://")):
        from modular_forge.persistence.mongo import MongoDatabase

        return MongoDatabase(settings.database_url, settings.mongodb_database, specs)
    from modular_forge.persistence.sql import SQLDatabase

    return SQLDatabase(settings.database_url, specs)


def create_app(
    settings: Settings | None = None, *, notifications=None, rate_store=None, database=None
):
    settings = settings or Settings()
    security = Security(settings)
    db = database or make_database(settings, table_specs(settings))
    rt = Runtime(settings, db, security, RateLimiter(settings, security, rate_store))

    @asynccontextmanager
    async def lifespan(app):
        try:
            await to_thread.run_sync(lambda: db.initialize(create=settings.auto_create_schema))
            for starter in rt.starters:
                await to_thread.run_sync(starter)
            if notifications is not None:
                rt.notifications = notifications
            yield
        finally:
            for closer in reversed(rt.closers):
                await to_thread.run_sync(closer)
            await to_thread.run_sync(rt.rate_limiter.store.close)
            await to_thread.run_sync(db.close)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.module_api_docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.module_api_docs_enabled else None,
    )
    app.state.runtime = rt
    app.include_router(auth_router)
    install_modules(app, rt)

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError):
        headers = {"Retry-After": str(error.retry_after)} if error.retry_after is not None else None
        return JSONResponse(
            {
                "error": {"code": error.code, "message": error.message},
                "request_id": request.state.request_id,
            },
            status_code=error.status,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        fields = [{"location": list(e["loc"]), "type": e["type"]} for e in error.errors()]
        return JSONResponse(
            {
                "error": {
                    "code": "validation_error",
                    "message": "Invalid request.",
                    "fields": fields,
                },
                "request_id": request.state.request_id,
            },
            status_code=422,
        )

    @app.get("/health/live", tags=["Health"])
    def liveness():
        return {"status": "up"}

    @app.get("/health/ready", tags=["Health"])
    def readiness():
        healthy = db.healthy() and rt.rate_limiter.store.healthy()
        return JSONResponse(
            {"status": "up" if healthy else "down"}, status_code=200 if healthy else 503
        )

    @app.get("/api/v1/modules", tags=["Modules"])
    def modules():
        return catalog(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-XSRF-TOKEN"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(SecurityMiddleware, runtime=rt)
    return app
