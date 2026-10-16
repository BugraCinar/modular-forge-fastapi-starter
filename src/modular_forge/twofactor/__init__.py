def install(app, runtime):
    from modular_forge.twofactor.routes import router
    from modular_forge.twofactor.service import TOTPService

    runtime.second_factor = TOTPService(runtime)
    app.include_router(router)
