"""Periodic SLA risk scanning and escalation worker."""
from __future__ import annotations

import asyncio

from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.services.sla_service import SLAService

logger = get_logger(__name__)


async def run_sla_monitor(interval_seconds: int) -> None:
    """Run an SLA scan periodically until the application shuts down."""
    while True:
        try:
            async with async_session_factory() as session:
                result = await SLAService.scan_incidents_and_auto_escalate(session)
            logger.info("SLA monitoring scan completed", **result)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("SLA monitoring scan failed")

        await asyncio.sleep(interval_seconds)
