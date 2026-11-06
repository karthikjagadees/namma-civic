"""Report the current complaint's SLA status; the scheduled worker escalates it."""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import select

from app.agents.state import CivicActionState
from app.core.database import async_session_factory
from app.models.complaint import Complaint
from app.services.sla_service import SLAService


async def monitoring_node(state: CivicActionState) -> Dict[str, Any]:
    """Use the existing SLA calculator and leave escalation to the periodic worker."""
    snapshot = state.get("sla_snapshot")
    complaint_id = state.get("complaint_id")
    if snapshot is None and complaint_id:
        async with async_session_factory() as session:
            complaint = await session.scalar(select(Complaint).where(Complaint.id == complaint_id))
            snapshot = SLAService.calculate_sla(complaint) if complaint else None
    result = {
        "status": snapshot.get("sla_status") if snapshot else "unavailable",
        "sla": snapshot,
        "delegated_to": "scheduled_sla_worker",
    }
    steps = list(state.get("steps_completed", []))
    if "monitoring" not in steps:
        steps.append("monitoring")
    return {"monitoring_result": result, "current_step": "resolution_verification", "steps_completed": steps}
