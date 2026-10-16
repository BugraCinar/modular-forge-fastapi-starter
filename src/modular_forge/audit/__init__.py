from modular_forge.audit.routes import router
from modular_forge.audit.service import DatabaseAudit


def install(app, runtime):
    runtime.audit = DatabaseAudit(runtime.database)
    app.include_router(router)
