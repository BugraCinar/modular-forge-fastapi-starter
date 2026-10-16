def install(app, runtime):
    from modular_forge.backup.routes import router
    from modular_forge.backup.service import BackupService

    runtime.backups = BackupService(runtime)
    app.include_router(router)
