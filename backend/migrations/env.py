"""
Alembic environment configuration for Namma Civic.
Reads DATABASE_URL from app settings so .env controls migrations.
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database import Base, runtime_database_url
from app.models import _import_all_models  # noqa: F401 — populates metadata

# ── Alembic Config ────────────────────────────────────────────
config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return runtime_database_url()


# ── Offline mode (generates SQL without connecting) ──────────

def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (connects to DB) ─────────────────────────────

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(get_url())
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
