"""
Namma Civic — Health Check API
GET /api/health
GET /api/health/detailed
"""
from __future__ import annotations

import platform
import sys
import time
from typing import Any, Dict

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal

router = APIRouter(tags=["health"])

# Track startup time for uptime calculation
_start_time = time.time()


@router.get("/health", summary="Basic health check")
async def health_check() -> Dict[str, Any]:
    """
    Basic liveness probe.
    Returns 200 OK when the service is running.
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env.value,
    }


@router.get("/health/detailed", summary="Detailed system status")
async def health_detailed() -> Dict[str, Any]:
    """
    Detailed health check including database connectivity.
    """
    uptime_seconds = round(time.time() - _start_time, 2)

    # ── Database connectivity ────────────────────────────────
    db_status = "ok"
    db_error: str | None = None
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = "error"
        db_error = str(exc)

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env.value,
        "uptime_seconds": uptime_seconds,
        "components": {
            "database": {
                "status": db_status,
                "mode": settings.database_mode.value,
                "error": db_error,
            },
            "ai": {
                "provider": settings.ai_provider.value,
                "mode": settings.ai_mode.value,
            },
            "mcp": {
                "mode": settings.mcp_mode.value,
            },
        },
        "system": {
            "python": sys.version,
            "platform": platform.system(),
        },
    }
