"""
Namma Civic — Health endpoint tests (Phase 1)
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_basic():
    """GET /api/health returns 200 with correct shape."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "Namma Civic"
    assert "version" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_detailed():
    """GET /api/health/detailed returns component status."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/health/detailed")

    assert response.status_code == 200
    data = response.json()
    assert "components" in data
    assert "database" in data["components"]
    assert "ai" in data["components"]
    assert "mcp" in data["components"]
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_health_fields():
    """Health response contains all required fields."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/health")

    data = response.json()
    required_fields = {"status", "service", "version", "environment"}
    assert required_fields.issubset(data.keys()), (
        f"Missing fields: {required_fields - data.keys()}"
    )


def test_vercel_database_url_is_writable(monkeypatch):
    """Alembic and the app must open the same file Vercel allows writes to."""
    monkeypatch.setenv("VERCEL", "1")
    from app.core.database import runtime_database_url

    assert runtime_database_url() == "sqlite+aiosqlite:////tmp/namma-civic.db"
