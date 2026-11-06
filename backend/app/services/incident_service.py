"""Small transactional helpers for the incident data model."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint, ComplaintStatus
from app.models.incident import Incident, IncidentStatus
from app.models.report_link import ReportLink, ReportLinkDecisionSource


def incident_status_for_report(status: ComplaintStatus) -> IncidentStatus:
    """Map the existing report lifecycle to a new incident's initial state."""
    if status == ComplaintStatus.resolved:
        return IncidentStatus.resolved
    if status in (ComplaintStatus.assigned, ComplaintStatus.in_progress):
        return IncidentStatus.in_progress
    if status == ComplaintStatus.rejected:
        return IncidentStatus.closed
    return IncidentStatus.open


async def create_initial_incident_for_report(
    session: AsyncSession,
    complaint: Complaint,
) -> Tuple[Incident, ReportLink]:
    """Create a one-report incident and its active provenance link atomically.

    This helper is used for new intake and demo seed reports before duplicate
    resolution is integrated. It never changes the source complaint fields.
    """
    incident = Incident(
        title=complaint.title,
        category=complaint.category,
        status=incident_status_for_report(complaint.status),
        latitude=complaint.latitude,
        longitude=complaint.longitude,
        address=complaint.address,
        landmark=complaint.landmark,
        location_confidence=complaint.location_confidence,
        location_accuracy_m=complaint.location_accuracy_m,
        created_at=complaint.created_at,
        updated_at=complaint.updated_at,
        resolved_at=complaint.resolved_at,
    )
    session.add(incident)
    await session.flush()

    link = ReportLink(
        complaint_id=complaint.id,
        incident_id=incident.id,
        decision_source=ReportLinkDecisionSource.auto,
        signal_evidence={
            "decision": "initial_incident",
            "reason": "Initial report association before duplicate resolution is integrated.",
        },
    )
    session.add(link)
    await session.flush()
    return incident, link


async def create_recurrence_incident_for_report(
    session: AsyncSession,
    complaint: Complaint,
    resolved_incident_id: str,
    match_score: float,
    signal_evidence: dict,
) -> Tuple[Incident, ReportLink]:
    """Create a fresh incident and supersede the report's provisional initial link.

    The prior resolved incident remains intact and is referenced by the new
    incident's recurrence pointer. The report itself remains unchanged.
    """
    old_link = await session.scalar(
        select(ReportLink)
        .where(ReportLink.complaint_id == complaint.id, ReportLink.is_active.is_(True))
        .with_for_update()
    )
    if old_link is None:
        raise ValueError(f"No active incident link exists for report {complaint.id}")
    resolved_incident = await session.get(Incident, resolved_incident_id)
    if resolved_incident is None or resolved_incident.status != IncidentStatus.resolved:
        raise ValueError(f"Recurrence target {resolved_incident_id} is not a resolved incident")

    incident = Incident(
        title=complaint.title,
        category=complaint.category,
        status=incident_status_for_report(complaint.status),
        latitude=complaint.latitude,
        longitude=complaint.longitude,
        address=complaint.address,
        landmark=complaint.landmark,
        location_confidence=complaint.location_confidence,
        location_accuracy_m=complaint.location_accuracy_m,
        created_at=complaint.created_at,
        updated_at=complaint.updated_at,
        recurrence_of_incident_id=resolved_incident.id,
    )
    session.add(incident)
    await session.flush()

    now = datetime.now(timezone.utc)
    old_link.is_active = False
    old_link.ended_at = now
    await session.flush()
    new_link = ReportLink(
        complaint_id=complaint.id,
        incident_id=incident.id,
        match_score=match_score,
        signal_evidence={**signal_evidence, "decision": "recurrence", "recurrence_of_incident_id": resolved_incident.id},
        decision_source=ReportLinkDecisionSource.auto,
        supersedes_link_id=old_link.id,
    )
    session.add(new_link)
    await session.flush()
    return incident, new_link


async def reassign_report_link(
    session: AsyncSession,
    link_id: str,
    new_incident_id: str,
    officer_id: str,
    decision_note: str,
    match_score: float | None = None,
    signal_evidence: dict | None = None,
) -> ReportLink:
    """Move a report to another incident while retaining the prior decision.

    Callers must commit or roll back the containing transaction. The old link
    is ended before the new active link is inserted to satisfy the unique
    active-link index; transaction rollback restores the old link on failure.
    """
    old_link = await session.scalar(
        select(ReportLink).where(ReportLink.id == link_id).with_for_update()
    )
    if old_link is None or not old_link.is_active:
        raise ValueError(f"Active report link {link_id} was not found")

    now = datetime.now(timezone.utc)
    old_link.is_active = False
    old_link.ended_at = now
    await session.flush()

    new_link = ReportLink(
        complaint_id=old_link.complaint_id,
        incident_id=new_incident_id,
        match_score=match_score,
        signal_evidence=signal_evidence or {},
        decision_source=ReportLinkDecisionSource.officer,
        is_active=True,
        supersedes_link_id=old_link.id,
        decided_by_id=officer_id,
        decision_note=decision_note,
    )
    session.add(new_link)
    await session.flush()
    return new_link
