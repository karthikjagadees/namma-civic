"""Shared fixtures that keep tests isolated from user data and external services."""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# Keep test SQLite data, uploads, and settings outside the checkout. Changing
# cwd before importing application settings also prevents accidental .env use.
_ORIGINAL_CWD = Path.cwd()
_TEST_RUNTIME_DIR = Path(tempfile.mkdtemp(prefix="namma-civic-tests-"))
os.chdir(_TEST_RUNTIME_DIR)
os.environ["DEBUG"] = "true"
os.environ["AI_MODE"] = "mock"
os.environ["AI_PROVIDER"] = "mock"
os.environ["MCP_MODE"] = "mock"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./namma-civic-test.db"

from app.core.ai.factory import get_ai_provider
from app.core.config import AIMode, settings
from app.core.database import engine, init_db


@pytest.fixture(scope="session", autouse=True)
async def initialize_test_database():
    """Create the schema and deterministic demo records before API tests run.

    HTTPX's ASGITransport does not start FastAPI's lifespan automatically, so
    the application's normal startup database initialization is skipped.
    """
    await init_db()
    yield
    await engine.dispose()
    os.chdir(_ORIGINAL_CWD)
    shutil.rmtree(_TEST_RUNTIME_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def use_mock_ai_provider(monkeypatch):
    monkeypatch.setattr(settings, "ai_mode", AIMode.mock)
    monkeypatch.setattr(settings, "ai_provider", AIMode.mock)
    get_ai_provider.cache_clear()
    yield
    get_ai_provider.cache_clear()
