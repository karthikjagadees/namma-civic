"""Classify a complaint against bounded incident candidates."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.agents.state import CivicActionState
from app.core.database import async_session_factory
from app.deduplication.engine import MatchDecision, MatchResult, ReportEvidence
from app.deduplication.repository import resolve_report_against_incidents

logger = logging.getLogger("namma-civic.agent.deduplication")


async def deduplication_node(state: CivicActionState) -> Dict[str, Any]:
    """Use the duplicate resolver and make every retrieval/signal failure reviewable."""
    complaint_id = state.get("complaint_id") or "unknown"
    logger.info("[DeduplicationAgent] Checking duplicates for complaint %s", complaint_id)
    reported_at = state.get("reported_at")
    if not isinstance(reported_at, datetime):
        reported_at = datetime.now(timezone.utc)
    report = ReportEvidence(
        report_id=complaint_id,
        text=f"{state.get('title', '')}\n{state.get('description', '')}".strip(),
        category=state.get("category", "other"),
        latitude=state.get("latitude"),
        longitude=state.get("longitude"),
        location_confidence=state.get("location_confidence"),
        location_accuracy_m=state.get("location_accuracy_m"),
        address=state.get("address"),
        landmark=state.get("landmark"),
        photo_hashes=tuple(state.get("photo_hashes", [])),
        channel=state.get("source"),
        reported_at=reported_at,
    )
    try:
        async with async_session_factory() as session:
            result = await resolve_report_against_incidents(session, report)
    except Exception as exc:
        logger.warning("Duplicate lookup failed; sending report to review (%s)", type(exc).__name__)
        result = MatchResult(
            MatchDecision.officer_review,
            reasons=("Incident candidate retrieval failed; officer review is required.",),
            failures=(f"{type(exc).__name__}: candidate retrieval failed",),
        )

    dedup_result = {
        "decision": result.decision.value,
        "is_duplicate": result.decision == MatchDecision.auto_link,
        "duplicate_of_id": result.incident_id,
        "incident_id": result.incident_id,
        "recurrence_of_incident_id": result.recurrence_of_incident_id,
        "best_score": result.best_score,
        "ranked_candidates": [
            {
                "incident_id": candidate.incident_id,
                "score": candidate.fused_score,
                "distance_m": candidate.distance_m,
                "signals": dict(candidate.signals),
            }
            for candidate in result.candidate_scores
        ],
        "reasons": list(result.reasons),
        "failures": list(result.failures),
    }
    steps = list(state.get("steps_completed", []))
    if "deduplication" not in steps:
        steps.append("deduplication")
    errors = list(state.get("errors", []))
    errors.extend(f"deduplication: {failure}" for failure in result.failures)
    return {
        "deduplication_result": dedup_result,
        "current_step": "routing",
        "steps_completed": steps,
        "errors": errors,
    }
