"""Alembic environment for Auto-DJ."""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from auto_dj.database.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

TARGET_METADATA = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("Keine Datenbank-URL für Alembic angegeben")

    context.configure(
        url=url,
        target_metadata=TARGET_METADATA,
        literal_binds=True,
        include_schemas=True,
        version_table_schema=config.get_main_option("version_table_schema"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("Keine Datenbank-URL für Alembic angegeben")

    connectable = create_engine(url)
    with connectable.connect() as connection:
        _prepare_schema(connection)
        context.configure(
            connection=connection,
            target_metadata=TARGET_METADATA,
            include_schemas=True,
            version_table_schema=config.get_main_option("version_table_schema"),
        )

        with context.begin_transaction():
            context.run_migrations()


def _prepare_schema(connection: Connection) -> None:
    schema = config.get_main_option("version_table_schema")
    if schema:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        connection.execute(text(f'SET search_path TO "{schema}"'))


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
