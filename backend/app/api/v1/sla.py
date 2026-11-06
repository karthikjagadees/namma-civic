"""
SLA Monitoring & Escalation API Endpoints
"""
import uuid
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.complaint import Complaint
from app.models.incident import Incident
from app.services.sla_service import SLAService

router = APIRouter(prefix="/sla", tags=["Autonomous SLA Monitoring"])


@router.get("/overview")
async def get_sla_overview(db: AsyncSession = Depends(get_db)):
    """Retrieve city-wide SLA compliance telemetry and breach metrics."""
    return await SLAService.get_sla_overview(db)


@router.get("/incidents/overview")
async def get_incident_sla_overview(db: AsyncSession = Depends(get_db)):
    """Return SLA metrics for shared incidents rather than individual reports."""
    return await SLAService.get_incident_sla_overview(db)


@router.get("/incident/{incident_id}")
async def get_incident_sla(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Return deadline and breach status for one incident."""
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return SLAService.calculate_incident_sla(incident)


@router.get("/complaint/{complaint_id}")
async def get_complaint_sla(complaint_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve fine-grained SLA countdown and risk level for a single complaint."""
    try:
        cid = uuid.UUID(complaint_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID")

    stmt = select(Complaint).where(Complaint.id == cid)
    res = await db.execute(stmt)
    complaint = res.scalar_one_or_none()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    return SLAService.calculate_sla(complaint)


@router.post("/check-and-escalate")
async def trigger_sla_scan_and_auto_escalate(db: AsyncSession = Depends(get_db)):
    """Autonomous batch agent trigger: scans active incidents and escalates at-risk cases."""
    return await SLAService.scan_incidents_and_auto_escalate(db)


@router.post("/escalate/{complaint_id}")
async def manual_escalate_complaint(
    complaint_id: str,
    payload: Dict[str, Any] = None,
    db: AsyncSession = Depends(get_db)
):
    """Manually escalate an urgent civic complaint to supervisor/director level."""
    try:
        cid = uuid.UUID(complaint_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID")

    stmt = select(Complaint).where(Complaint.id == cid).options(selectinload(Complaint.timeline))
    res = await db.execute(stmt)
    complaint = res.scalar_one_or_none()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    reason = (payload or {}).get("reason", "Manual Officer Escalation Protocol")
    tier = (payload or {}).get("tier", "TIER_1_SUPERVISOR")

    return await SLAService.escalate_complaint(db, complaint, reason=reason, tier=tier)
