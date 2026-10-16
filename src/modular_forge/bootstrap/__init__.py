def install(app, runtime):
    from modular_forge.identity.service import create_account

    with runtime.database.transaction() as tx:
        if tx.one("accounts", username=runtime.settings.seed_admin_username.lower()):
            return
        create_account(
            tx,
            runtime.settings.seed_admin_email,
            runtime.settings.seed_admin_username,
            runtime.security.hash_password(runtime.settings.seed_admin_password),
            role="SUPER_ADMIN",
            verified=True,
        )
