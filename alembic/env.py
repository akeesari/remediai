from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import packages.data_access.models  # noqa: F401 — registers all ORM models with Base.metadata
from alembic import context
from packages.data_access.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_env = os.environ.get("APP_ENV", "development")
database_url: str = os.environ.get("DATABASE_URL", "")

if not database_url:
    if _env == "production":
        raise RuntimeError(
            "DATABASE_URL environment variable must be set in production. "
            "See .env.example for the expected format."
        )
    # Local-dev fallback only — never use in staging or production
    database_url = "postgresql+asyncpg://remediai:change_me_locally@localhost:5432/remediai"


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=False,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
