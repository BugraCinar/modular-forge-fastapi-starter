from modular_forge.profile.routes import router


def install(app, runtime):
    app.include_router(router)
