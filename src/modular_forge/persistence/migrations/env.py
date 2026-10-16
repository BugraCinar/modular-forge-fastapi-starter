from alembic import context


def run():
    connection = context.config.attributes.get("connection")
    if connection is None:
        from modular_forge.persistence.sql import SQLDatabase
        from modular_forge.shared.config import Settings

        database = SQLDatabase(Settings().database_url, [])
        with database.engine.begin() as connection:
            configure(connection)
        database.close()
    else:
        configure(connection)


def configure(connection):
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


run()
