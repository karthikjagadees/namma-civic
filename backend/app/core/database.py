"""
Namma Civic — Database Layer
Abstraction over SQLite (dev) and PostgreSQL + PostGIS (prod).
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import AsyncGenerator

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import AppEnv, settings


_LEGACY_BASELINE_TABLES = {
    "users",
    "departments",
    "complaints",
    "complaint_media",
    "complaint_timeline",
    "ai_analyses",
}


# ── Base class for all ORM models ────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


def is_running_on_vercel() -> bool:
    """Detect whether app is executing inside Vercel serverless environment."""
    return (
        os.environ.get("VERCEL") == "1"
        or bool(os.environ.get("VERCEL_REGION"))
        or bool(os.environ.get("VERCEL_ENV"))
        or bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    )


def runtime_database_url() -> str:
    """Return the SQLAlchemy URL this process can actually open.

    Vercel can write only under ``/tmp``. The application engine and Alembic
    must share that file, or migrations create tables the login query never sees.
    """
    url = settings.database_url
    if settings.is_sqlite:
        if is_running_on_vercel() and "/tmp" not in url:
            return "sqlite+aiosqlite:////tmp/namma-civic.db"
        if url.startswith("sqlite:///") and "+aiosqlite" not in url:
            return url.replace("sqlite:///", "sqlite+aiosqlite:///")
        return url

    if url.startswith("postgresql://") and "+asyncpg" not in url and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+psycopg://")
    return url


def _build_engine():
    """
    Build an async SQLAlchemy engine from DATABASE_URL.

    SQLite:
        - Uses aiosqlite driver
        - Automatically adds check_same_thread=False
        - Returns synchronous-compatible async engine

    PostgreSQL:
        - Uses psycopg async driver
        - Supports PostGIS via geoalchemy2
    """
    url = runtime_database_url()

    if settings.is_sqlite:
        engine = create_async_engine(
            url,
            echo=settings.debug,
            connect_args={"check_same_thread": False, "timeout": 30},
        )
    else:
        engine = create_async_engine(
            url,
            echo=settings.debug,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )

    return engine


engine = _build_engine()

# ── Session factory ──────────────────────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Convenience alias for background tasks and agent pipelines
async_session_factory = AsyncSessionLocal


def _run_alembic_command(action: str, revision: str) -> None:
    """Run one Alembic command in a worker thread's event loop."""
    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "migrations"))
    command_fn = getattr(command, action)
    command_fn(config, revision)


async def _upgrade_schema() -> None:
    """Upgrade fresh schemas and adopt complete unversioned legacy schemas."""
    async with engine.connect() as connection:
        table_names = await connection.run_sync(
            lambda sync_connection: set(inspect(sync_connection).get_table_names())
        )

    if "alembic_version" not in table_names and table_names:
        if not _LEGACY_BASELINE_TABLES.issubset(table_names):
            missing = sorted(_LEGACY_BASELINE_TABLES - table_names)
            raise RuntimeError(
                "Refusing to stamp a partial unversioned schema; "
                f"missing baseline tables: {', '.join(missing)}"
            )
        await asyncio.to_thread(_run_alembic_command, "stamp", "0001_baseline")

    await asyncio.to_thread(_run_alembic_command, "upgrade", "head")


# ── Dependency injection helper ───────────────────────────────────────────────

_db_ready = False
_db_lock: asyncio.Lock | None = None


async def ensure_database() -> None:
    """Create tables and demo accounts once per process.

    Vercel's Python runtime does not always run the FastAPI lifespan before
    the first request. Login then queries an empty database and fails.
    """
    global _db_ready, _db_lock
    if _db_ready:
        return
    if _db_lock is None:
        _db_lock = asyncio.Lock()
    async with _db_lock:
        if _db_ready:
            return
        await init_db()
        _db_ready = True


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session.

    Usage:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    await ensure_database()
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Database initialisation ───────────────────────────────────────────────────

async def init_db() -> None:
    """
    Apply Alembic schema revisions and seed demo data outside production.

    Complete schemas created by earlier ``create_all()`` releases are stamped
    at the baseline revision before applying newer migrations.
    """
    from app.models import _import_all_models
    _import_all_models()
    await _upgrade_schema()

    is_vercel = is_running_on_vercel()
    auto_seed = os.environ.get("AUTO_SEED", "").lower() in ("true", "1", "yes")

    if settings.app_env != AppEnv.production or (is_vercel and settings.is_sqlite) or auto_seed:
        async with AsyncSessionLocal() as session:
            try:
                from app.core.seed import seed_all
                await seed_all(session)
                await session.commit()
            except Exception as e:
                await session.rollback()
                from app.core.logging import get_logger
                get_logger(__name__).warning("Database seeding skipped or encountered issue", error=str(e))
