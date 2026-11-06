"""Public incident tracker and authenticated lifecycle actions."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, RequireOfficer
from app.core.tracking import normalize_tracking_id
from app.models.incident import IncidentStatus
from app.models.complaint import Complaint
from app.models.report_link import ReportLink
from app.models.user import UserRole
from app.services.incident_follow_up_service import IncidentFollowUpService

router = APIRouter(prefix="/incidents", tags=["Incidents"])


class IncidentDisputeRequest(BaseModel):
    """Citizen note explaining why a resolved incident remains unresolved."""

    reason: str = Field(..., min_length=5, max_length=1000)


class IncidentStatusRequest(BaseModel):
    """Officer incident-state update with a public timeline note."""

    status: IncidentStatus
    note: str = Field(..., min_length=3, max_length=1000)


@router.get("/{incident_id}/tracker")
async def get_public_incident_tracker(incident_id: str, db: DBSession):
    """Return public operational status and aggregate report count only."""
    try:
        return await IncidentFollowUpService.get_public_tracker(db, incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/track/{tracking_id}")
async def track_by_tracking_id(tracking_id: str, db: DBSession):
    """Public lookup of a report's shared incident by its citizen-facing tracking ID.

    Malformed and unknown IDs return the same 404 so the endpoint cannot be used
    to probe which IDs exist. Only public incident fields are returned.
    """
    not_found = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No report found for that tracking ID",
    )
    code = normalize_tracking_id(tracking_id)
    if code is None:
        raise not_found
    row = await db.execute(
        select(Complaint.id, Complaint.created_at, ReportLink.incident_id)
        .join(ReportLink, ReportLink.complaint_id == Complaint.id)
        .where(Complaint.tracking_id == code, ReportLink.is_active.is_(True))
    )
    found = row.first()
    if found is None:
        raise not_found
    _, submitted_at, incident_id = found
    tracker = await IncidentFollowUpService.get_public_tracker(db, incident_id)
    return {"tracking_id": code, "submitted_at": submitted_at.isoformat(), **tracker}


@router.get("/by-report/{complaint_id}/tracker")
async def get_tracker_for_linked_report(complaint_id: str, current_user: CurrentUser, db: DBSession):
    """Resolve a citizen's own report to its public incident tracker."""
    row = await db.execute(
        select(ReportLink.incident_id, Complaint.citizen_id)
        .join(Complaint, Complaint.id == ReportLink.complaint_id)
        .where(ReportLink.complaint_id == complaint_id, ReportLink.is_active.is_(True))
    )
    incident_id, citizen_id = row.one_or_none() or (None, None)
    if incident_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident link not found")
    if citizen_id != current_user.id and current_user.role not in (UserRole.officer, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident link not found")
    return await IncidentFollowUpService.get_public_tracker(db, incident_id)


@router.post("/{incident_id}/dispute")
async def dispute_resolved_incident(
    incident_id: str,
    payload: IncidentDisputeRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Let a linked citizen dispute resolution and reopen the shared incident."""
    try:
        return await IncidentFollowUpService.dispute_and_reopen(
            db, incident_id, current_user.id, payload.reason,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        code = status.HTTP_404_NOT_FOUND if str(exc) == "Incident not found" else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=str(exc))


@router.patch("/{incident_id}/status")
async def change_incident_status(
    incident_id: str,
    payload: IncidentStatusRequest,
    current_user: RequireOfficer,
    db: DBSession,
):
    """Change shared incident status and fan the update out to linked reporters."""
    try:
        result = await IncidentFollowUpService.change_status(
            db, incident_id, payload.status, actor_id=current_user.id, note=payload.note,
        )
        return {"incident_id": incident_id, "status": payload.status.value, **result}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
