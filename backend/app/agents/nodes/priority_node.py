"""Increase incident urgency using independent reports and intake severity."""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import distinct, select

from app.agents.state import CivicActionState
from app.core.database import async_session_factory
from app.models.complaint import Complaint
from app.models.report_link import ReportLink

_LEVELS = ("low", "medium", "high", "critical")


def _priority_index(priority: str) -> int:
    """Return a safe priority rank, treating unknown values as medium."""
    try:
        return _LEVELS.index(priority.lower())
    except ValueError:
        return 1


async def priority_node(state: CivicActionState) -> Dict[str, Any]:
    """Count independent linked reporters, raising priority at three and every two after."""
    dedup = state.get("deduplication_result", {})
    incident_id = dedup.get("incident_id")
    count = state.get("incident_report_count")
    if count is None:
        count = 1
        if incident_id:
            async with async_session_factory() as session:
                reporters = set((await session.scalars(
                    select(distinct(Complaint.citizen_id))
                    .join(ReportLink, ReportLink.complaint_id == Complaint.id)
                    .where(
                        ReportLink.incident_id == incident_id,
                        ReportLink.is_active.is_(True),
                    )
                )).all())
                reporter_id = await session.scalar(
                    select(Complaint.citizen_id).where(Complaint.id == state.get("complaint_id"))
                )
            if reporter_id:
                reporters.add(reporter_id)
            count = max(1, len(reporters))

    routing = dict(state.get("routing_result", {}))
    base_priority = routing.get("priority", "medium")
    # Three independent citizens trigger the first boost; each two additional
    # reports can add one more level, capped at critical.
    extra_report_levels = max(0, (max(1, int(count)) - 1) // 2)
    rank = min(len(_LEVELS) - 1, _priority_index(base_priority) + extra_report_levels)
    priority = _LEVELS[rank]
    routing["priority"] = priority
    routing["sla_hours"] = {"critical": 12, "high": 24, "medium": 48, "low": 72}[priority]
    needs_approval = bool(state.get("requires_human_approval", False))
    approval_reason = state.get("approval_reason", "")
    if priority == "critical" and not needs_approval:
        needs_approval = True
        approval_reason = "Aggregate independent reports raised incident priority to critical."
    result = {
        "priority": priority,
        "base_priority": base_priority,
        "report_count": max(1, int(count)),
        "independent_report_boost_levels": extra_report_levels,
        "rule": "one priority level at three independent reports, then for each two additional reports; cap at critical",
    }
    steps = list(state.get("steps_completed", []))
    if "priority" not in steps:
        steps.append("priority")
    return {
        "priority_result": result,
        "routing_result": routing,
        "requires_human_approval": needs_approval,
        "approval_reason": approval_reason,
        "is_awaiting_approval": needs_approval and state.get("human_decision") is None,
        "current_step": "routing",
        "steps_completed": steps,
    }


