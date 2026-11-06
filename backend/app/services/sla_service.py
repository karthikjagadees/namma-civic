"""
Autonomous SLA Monitoring & Auto-Escalation Engine
Tracks complaint resolution deadlines, predicts breach risks, and executes escalations.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.mcp.client import mcp_client
from app.models.complaint import Complaint, ComplaintStatus, ComplaintTimeline, PriorityLevel
from app.models.follow_up import IncidentTimeline
from app.models.incident import Incident, IncidentStatus
from app.models.work_order import WorkOrder

logger = get_logger(__name__)


SLA_HOURS_MAP = {
    PriorityLevel.critical: 12,
    PriorityLevel.high: 24,
    PriorityLevel.medium: 48,
    PriorityLevel.low: 72,
}


class SLAService:
    """Computes SLA compliance metrics and executes automated escalations."""

    @staticmethod
    def calculate_sla(complaint: Complaint) -> Dict[str, Any]:
        """Compute SLA deadline, time left, and breach status for a complaint."""
        created_at = complaint.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        priority = complaint.priority or PriorityLevel.medium
        total_sla_hours = SLA_HOURS_MAP.get(priority, 48)
        deadline = created_at + timedelta(hours=total_sla_hours)

        now = datetime.now(timezone.utc)
        
        # If already resolved/rejected, use actual completion
        is_closed = complaint.status in (ComplaintStatus.resolved, ComplaintStatus.rejected)
        
        time_elapsed_seconds = max(0, (now - created_at).total_seconds())
        time_remaining_seconds = (deadline - now).total_seconds()
        total_sla_seconds = total_sla_hours * 3600

        percent_consumed = min(100.0, max(0.0, (time_elapsed_seconds / total_sla_seconds) * 100))
        hours_remaining = round(time_remaining_seconds / 3600, 1)

        if is_closed:
            sla_status = "RESOLVED"
            risk_level = "NONE"
        elif time_remaining_seconds <= 0:
            sla_status = "BREACHED"
            risk_level = "CRITICAL"
        elif percent_consumed >= 75.0 or hours_remaining <= (total_sla_hours * 0.25):
            sla_status = "AT_RISK"
            risk_level = "HIGH"
        else:
            sla_status = "ON_TRACK"
            risk_level = "LOW"

        return {
            "complaint_id": str(complaint.id),
            "priority": priority.value,
            "total_sla_hours": total_sla_hours,
            "created_at": created_at.isoformat(),
            "deadline": deadline.isoformat(),
            "hours_remaining": hours_remaining,
            "seconds_remaining": max(0, int(time_remaining_seconds)),
            "percent_consumed": round(percent_consumed, 1),
            "sla_status": sla_status,
            "risk_level": risk_level,
            "is_closed": is_closed,
        }

    @staticmethod
    def calculate_incident_sla(incident: Incident) -> Dict[str, Any]:
        """Calculate deadline and risk once for the shared civic incident."""
        created_at = incident.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        priority = incident.priority or "medium"
        total_hours = {"critical": 12, "high": 24, "medium": 48, "low": 72}.get(priority, 48)
        deadline = created_at + timedelta(hours=total_hours)
        remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
        elapsed = max(0.0, (datetime.now(timezone.utc) - created_at).total_seconds())
        percent = min(100.0, (elapsed / (total_hours * 3600)) * 100)
        closed = incident.status in (IncidentStatus.resolved, IncidentStatus.closed)
        status = "RESOLVED" if closed else "BREACHED" if remaining <= 0 else "AT_RISK" if percent >= 75 else "ON_TRACK"
        return {
            "incident_id": incident.id,
            "priority": priority,
            "total_sla_hours": total_hours,
            "created_at": created_at.isoformat(),
            "deadline": deadline.isoformat(),
            "hours_remaining": round(remaining / 3600, 1),
            "percent_consumed": round(percent, 1),
            "sla_status": status,
            "risk_level": "NONE" if closed else "CRITICAL" if status == "BREACHED" else "HIGH" if status == "AT_RISK" else "LOW",
            "is_closed": closed,
        }

    @staticmethod
    async def escalate_incident(
        session: AsyncSession,
        incident: Incident,
        *,
        reason: str,
        tier: str,
    ) -> Dict[str, Any]:
        """Persist an incident-level escalation audit and notify municipal staff."""
        if incident.status in (IncidentStatus.resolved, IncidentStatus.closed):
            return {"status": "SKIPPED", "message": "Incident is already closed"}
        if incident.priority == "medium":
            incident.priority = "high"
        for order in (await session.scalars(select(WorkOrder).where(WorkOrder.incident_id == incident.id))).all():
            order.priority = incident.priority
        session.add(IncidentTimeline(
            incident_id=incident.id,
            event_type="sla_escalation",
            status=incident.status.value,
            note=f"SLA escalation {tier}: {reason}. Priority is {incident.priority}.",
        ))
        await session.commit()
        alert_error = None
        try:
            await mcp_client.call_tool("notify_officer_emergency_alert", {
                "alert_title": f"SLA ESCALATION: Incident {incident.id[:8].upper()}",
                "hazard_description": reason,
                "sla_hours_left": 0,
            })
        except Exception as exc:
            alert_error = f"{type(exc).__name__}: alert failed"
            logger.exception("Incident SLA escalation alert failed for %s", incident.id)
        return {"status": "ESCALATED", "incident_id": incident.id, "tier": tier, "alert_error": alert_error}

    @staticmethod
    async def scan_incidents_and_auto_escalate(session: AsyncSession) -> Dict[str, Any]:
        """Scan active incidents once each and persist an escalation per risk tier."""
        incidents = list((await session.scalars(select(Incident).where(
            Incident.status.in_((IncidentStatus.open, IncidentStatus.in_progress))
        ))).all())
        timeline = list((await session.scalars(select(IncidentTimeline).where(
            IncidentTimeline.event_type == "sla_escalation"
        ))).all())
        notes_by_incident: dict[str, list[str]] = {}
        for event in timeline:
            notes_by_incident.setdefault(event.incident_id, []).append(event.note)
        escalations = []
        for incident in incidents:
            sla = SLAService.calculate_incident_sla(incident)
            if sla["sla_status"] not in ("AT_RISK", "BREACHED"):
                continue
            tier = "TIER_2_DIRECTOR" if sla["sla_status"] == "BREACHED" else "TIER_1_SUPERVISOR"
            if any(tier in note for note in notes_by_incident.get(incident.id, [])):
                continue
            reason = f"Incident SLA {sla['sla_status']}: {sla['hours_remaining']}h remaining"
            result = await SLAService.escalate_incident(session, incident, reason=reason, tier=tier)
            if result["status"] == "ESCALATED":
                escalations.append({"incident_id": incident.id, "status": sla["sla_status"], "tier": tier})
        return {
            "total_scanned": len(incidents),
            "escalated_count": len(escalations),
            "escalations": escalations,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    async def get_incident_sla_overview(session: AsyncSession) -> Dict[str, Any]:
        """Summarize incident-level on-track, at-risk, breached, and resolved counts."""
        incidents = list((await session.scalars(select(Incident))).all())
        counts = {"ON_TRACK": 0, "AT_RISK": 0, "BREACHED": 0, "RESOLVED": 0}
        for incident in incidents:
            counts[SLAService.calculate_incident_sla(incident)["sla_status"]] += 1
        return {"total_incidents": len(incidents), **{key.lower(): value for key, value in counts.items()}}

    @staticmethod
    async def escalate_complaint(
        session: AsyncSession,
        complaint: Complaint,
        reason: str = "Autonomous SLA Proximity Alert",
        tier: str = "TIER_1_SUPERVISOR"
    ) -> Dict[str, Any]:
        """Trigger formal escalation, log audit note, and dispatch officer emergency alert via MCP."""
        now = datetime.now(timezone.utc)
        
        # Disallow redundant escalations if already resolved
        if complaint.status in (ComplaintStatus.resolved, ComplaintStatus.rejected):
            return {"status": "SKIPPED", "message": "Complaint is already resolved/closed"}

        # Optional priority bump if medium
        if complaint.priority == PriorityLevel.medium:
            complaint.priority = PriorityLevel.high

        tracking_code = str(getattr(complaint, "tracking_id", None) or complaint.id[:8].upper())
        escalation_note = (
            f"⚠️ AUTONOMOUS SLA ESCALATION ({tier}): {reason}. "
            f"Priority calibrated to {complaint.priority.value.upper()}. "
            f"Dispatched automated alert to municipal command staff."
        )

        timeline_entry = ComplaintTimeline(
            complaint_id=complaint.id,
            status=complaint.status,
            note=escalation_note,
        )
        session.add(timeline_entry)
        await session.commit()

        # Send alert via MCP
        mcp_alert = {}
        mcp_alert_error = None
        try:
            mcp_alert = await mcp_client.call_tool("notify_officer_emergency_alert", {
                "alert_title": f"SLA ESCALATION: Complaint {tracking_code}",
                "hazard_description": reason,
                "sla_hours_left": 1.5,
            })
        except Exception as exc:
            mcp_alert_error = str(exc)
            logger.exception(
                "Failed to dispatch SLA escalation alert",
                complaint_id=str(complaint.id),
                tier=tier,
            )

        return {
            "status": "ESCALATED",
            "tier": tier,
            "complaint_id": str(complaint.id),
            "tracking_id": tracking_code,
            "new_priority": complaint.priority.value,
            "escalated_at": now.isoformat(),
            "mcp_alert": mcp_alert,
            "mcp_alert_error": mcp_alert_error,
        }

    @staticmethod
    async def scan_and_auto_escalate(session: AsyncSession) -> Dict[str, Any]:
        """Scan all active complaints and automatically trigger escalations for AT_RISK or BREACHED cases."""
        stmt = (
            select(Complaint)
            .where(Complaint.status.in_([ComplaintStatus.pending, ComplaintStatus.in_progress, ComplaintStatus.assigned]))
            .options(selectinload(Complaint.timeline))
        )
        result = await session.execute(stmt)
        complaints = result.scalars().all()

        total_scanned = len(complaints)
        escalated_count = 0
        details = []
        recorded_escalations = session.info.setdefault("sla_escalations_recorded", set())

        for c in complaints:
            sla_info = SLAService.calculate_sla(c)
            if sla_info["sla_status"] in ("AT_RISK", "BREACHED"):
                tier = "TIER_2_DIRECTOR" if sla_info["sla_status"] == "BREACHED" else "TIER_1_SUPERVISOR"
                escalation_key = (str(c.id), tier)
                already_escalated = any(
                    event.note
                    and "AUTONOMOUS SLA ESCALATION" in event.note
                    and f"({tier})" in event.note
                    for event in c.timeline
                )
                if already_escalated or escalation_key in recorded_escalations:
                    continue

                reason = f"SLA {sla_info['sla_status']}: {sla_info['hours_remaining']}h remaining ({sla_info['percent_consumed']}% consumed)"
                result = await SLAService.escalate_complaint(session, c, reason=reason, tier=tier)
                if result["status"] != "ESCALATED":
                    continue

                recorded_escalations.add(escalation_key)
                escalated_count += 1
                details.append({
                    "tracking_id": c.tracking_id,
                    "status": sla_info["sla_status"],
                    "tier": tier,
                    "hours_remaining": sla_info["hours_remaining"]
                })

        return {
            "total_scanned": total_scanned,
            "escalated_count": escalated_count,
            "escalations": details,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }

    @staticmethod
    async def get_sla_overview(session: AsyncSession) -> Dict[str, Any]:
        """City-wide SLA performance summary."""
        stmt = select(Complaint).options(selectinload(Complaint.timeline))
        result = await session.execute(stmt)
        all_complaints = result.scalars().all()

        total = len(all_complaints)
        on_track = 0
        at_risk = 0
        breached = 0
        resolved_count = 0

        for c in all_complaints:
            sla = SLAService.calculate_sla(c)
            if sla["sla_status"] == "RESOLVED":
                resolved_count += 1
            elif sla["sla_status"] == "BREACHED":
                breached += 1
            elif sla["sla_status"] == "AT_RISK":
                at_risk += 1
            else:
                on_track += 1

        active_count = on_track + at_risk + breached
        compliance_rate = round(((on_track + resolved_count) / max(1, total)) * 100, 1)

        return {
            "total_complaints": total,
            "active_complaints": active_count,
            "on_track": on_track,
            "at_risk": at_risk,
            "breached": breached,
            "resolved": resolved_count,
            "sla_compliance_rate": compliance_rate,
            "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        }
