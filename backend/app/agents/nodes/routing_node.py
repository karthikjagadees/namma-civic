"""
Namma Civic — Routing Agent Node
Determines responsible municipal department, computes SLA, and triggers Human-in-the-Loop policies.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlalchemy import select

from app.agents.state import CivicActionState
from app.core.database import async_session_factory
from app.models.department import Department

logger = logging.getLogger("namma-civic.agent.routing")

CATEGORY_TO_DEPT = {
    "pothole": "ROADS",
    "garbage": "SANITATION",
    "water_leakage": "WATER",
    "street_light": "ELECTRICAL",
    "drainage": "DRAINAGE",
    "traffic_signal": "ROADS",
    "encroachment": "PUBLIC_WORKS",
    "other": "PUBLIC_WORKS",
    "ROADS": "ROADS",
    "SANITATION": "SANITATION",
    "WATER_SUPPLY": "WATER",
    "WATER": "WATER",
    "STREETLIGHTS": "ELECTRICAL",
    "ELECTRICAL": "ELECTRICAL",
    "DRAINAGE": "DRAINAGE",
    "PARKS": "PUBLIC_WORKS",
    "TRAFFIC": "ROADS",
}

SLA_MAP = {
    "critical": 12,
    "high": 24,
    "medium": 48,
    "low": 72,
}


async def routing_node(state: CivicActionState) -> Dict[str, Any]:
    """
    Routing node: Identifies department, calculates priority & SLA, and flags HITL requirements.
    """
    complaint_id = state.get("complaint_id")
    logger.info(f"[RoutingAgent] Calculating routing & SLA for complaint {complaint_id}")

    intake = state.get("intake_result", {})
    validation = state.get("validation_result", {})
    dedup = state.get("deduplication_result", {})

    detected_cat = intake.get("detected_category") or state.get("category", "other")
    dept_code = CATEGORY_TO_DEPT.get(detected_cat, "PUBLIC_WORKS")

    # Fetch Department from DB to get ID and official name
    dept_name = "Public Works & Infrastructure"
    dept_id = None
    try:
        async with async_session_factory() as session:
            stmt = select(Department).where(Department.code == dept_code)
            res = await session.execute(stmt)
            dept = res.scalar_one_or_none()
            if dept:
                dept_id = dept.id
                dept_name = dept.name
    except Exception as exc:
        logger.warning(f"Error querying department {dept_code}: {exc}")

    # Determine Severity & Priority
    severity = intake.get("severity", 5)
    urgency_score = intake.get("urgency_score", 0.5)

    if severity >= 8 or urgency_score >= 0.85:
        priority = "critical"
    elif severity >= 6 or urgency_score >= 0.65:
        priority = "high"
    elif severity >= 4:
        priority = "medium"
    else:
        priority = "low"

    sla_hours = SLA_MAP.get(priority, 48)

    # Assess Human-in-the-Loop (HITL) Gate
    requires_human_approval = False
    reasons = []

    if dedup.get("decision") == "officer_review":
        requires_human_approval = True
        reasons.append("Duplicate match requires officer review: " + "; ".join(dedup.get("reasons", [])))
    if intake.get("provider_failed"):
        requires_human_approval = True
        reasons.append("AI provider failed; officer review is required before routing.")

    if priority == "critical" or severity >= 8:
        requires_human_approval = True
        reasons.append(f"High risk emergency (Severity: {severity}/10, Priority: {priority})")

    if not validation.get("is_valid"):
        requires_human_approval = True
        reasons.append(f"Suspicious report / Spam flag ({validation.get('validity_reason')})")

    if intake.get("confidence_score", 1.0) < 0.70:
        requires_human_approval = True
        reasons.append(f"Low AI confidence ({int(intake.get('confidence_score', 0) * 100)}%)")

    approval_reason = "; ".join(reasons) if requires_human_approval else "Auto-approved by autonomous policy."

    routing_result = {
        "department_id": dept_id,
        "department_name": dept_name,
        "department_code": dept_code,
        "priority": priority,
        "severity": severity,
        "sla_hours": sla_hours,
        "routing_rationale": (
            f"Mapped '{detected_cat}' to {dept_name} with target {sla_hours}h SLA based on {priority} priority."
        ),
    }

    steps = list(state.get("steps_completed", []))
    if "routing" not in steps:
        steps.append("routing")

    return {
        "routing_result": routing_result,
        "requires_human_approval": requires_human_approval,
        "approval_reason": approval_reason,
        "is_awaiting_approval": requires_human_approval and state.get("human_decision") is None,
        "current_step": "approval" if requires_human_approval else "action",
        "steps_completed": steps,
    }
