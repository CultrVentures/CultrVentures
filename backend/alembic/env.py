"""
CULTR Ventures — Alembic Environment Configuration
Supports async PostgreSQL via asyncpg.
"""

import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy import create_engine

from alembic import context

# Alembic Config object
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import models for autogenerate support
# TODO: Import Base from models when SQLAlchemy models are defined
# from app.models.base import Base
# target_metadata = Base.metadata
target_metadata = None

# Override sqlalchemy.url from environment
database_url = os.getenv(
    "DATABASE_URL",
    config.get_main_option("sqlalchemy.url"),
)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL without DB connection."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to database."""
    connectable = create_engine(database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
