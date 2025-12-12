from logging.config import fileConfig

from alembic import context

from actidoo_wfe.database import metadata
from actidoo_wfe.database_models import load_all_models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

load_all_models()

target_metadata = metadata


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    engine = config.attributes["engine"]

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=False,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
