from modular_forge.admin.routes import router


def install(app, runtime):
    app.include_router(router)
