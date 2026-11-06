"""Incident tracker, reporter preferences, lifecycle notifications, and disputes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint, ComplaintStatus
from app.models.department import Department
from app.models.follow_up import IncidentNotificationPreference, IncidentTimeline, NotificationDelivery
from app.models.incident import Incident, IncidentStatus
from app.models.report_link import ReportLink
from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderStatus
from app.services.sla_service import SLAService


class IncidentFollowUpService:
    """Own incident-safe public information and reporter notification fan-out."""

    @staticmethod
    async def get_public_tracker(session: AsyncSession, incident_id: str) -> Dict[str, Any]:
        """Return public incident fields without complaint text or reporter identity."""
        incident = await session.get(Incident, incident_id)
        if incident is None:
            raise ValueError("Incident not found")
        reporter_count = int(await session.scalar(
            select(func.count(func.distinct(Complaint.citizen_id)))
            .join(ReportLink, ReportLink.complaint_id == Complaint.id)
            .where(ReportLink.incident_id == incident.id, ReportLink.is_active.is_(True))
        ) or 0)
        timeline_rows = (await session.scalars(
            select(IncidentTimeline)
            .where(IncidentTimeline.incident_id == incident.id)
            .order_by(IncidentTimeline.created_at, IncidentTimeline.id)
        )).all()
        work_order = await session.scalar(
            select(WorkOrder).where(WorkOrder.incident_id == incident.id).order_by(WorkOrder.created_at.desc())
        )
        department = await session.get(Department, work_order.department_id) if work_order and work_order.department_id else None
        sla = SLAService.calculate_incident_sla(incident)
        return {
            "incident_id": incident.id,
            "title": incident.title,
            "category": incident.category.value,
            "status": incident.status.value,
            "priority": incident.priority,
            "reporter_count": reporter_count,
            "responsible_department": department.name if department else None,
            "expected_by": sla["deadline"],
            "sla_status": sla["sla_status"],
            "what_happens_next": _next_step(incident.status),
            "timeline": [
                {
                    "status": event.status,
                    "event": event.event_type,
                    "note": _public_event_note(event.event_type, event.status),
                    "created_at": event.created_at.isoformat(),
                }
                for event in timeline_rows
            ],
        }

    @staticmethod
    async def notify_reporters(
        session: AsyncSession,
        incident: Incident,
        *,
        event_type: str,
        message: str,
        event_key: Optional[str] = None,
        recipient_user_ids: Optional[set[str]] = None,
    ) -> Dict[str, int]:
        """Fan out through opted-in channels and persist every delivery attempt."""
        from app.mcp.client import mcp_client

        stable_event_key = event_key or f"{event_type}:{incident.id}:{incident.updated_at.isoformat()}"
        rows = (await session.execute(
            select(User, IncidentNotificationPreference)
            .join(Complaint, Complaint.citizen_id == User.id)
            .join(ReportLink, ReportLink.complaint_id == Complaint.id)
            .outerjoin(IncidentNotificationPreference, IncidentNotificationPreference.user_id == User.id)
            .where(ReportLink.incident_id == incident.id, ReportLink.is_active.is_(True))
            .order_by(User.id)
        )).all()
        recipients = {user.id: (user, preference) for user, preference in rows}
        if recipient_user_ids is not None:
            recipients = {uid: pair for uid, pair in recipients.items() if uid in recipient_user_ids}
        deliveries: list[NotificationDelivery] = []
        for user, preference in recipients.values():
            channels = []
            if user.phone and (preference is None or preference.sms_enabled):
                channels.append("sms")
            if user.email and (preference is None or preference.email_enabled):
                channels.append("email")
            for channel in channels:
                prior = await session.scalar(select(NotificationDelivery).where(
                    NotificationDelivery.incident_id == incident.id,
                    NotificationDelivery.recipient_user_id == user.id,
                    NotificationDelivery.event_key == stable_event_key,
                    NotificationDelivery.channel == channel,
                ))
                if prior is None:
                    prior = NotificationDelivery(
                        incident_id=incident.id,
                        recipient_user_id=user.id,
                        event_key=stable_event_key,
                        event_type=event_type,
                        channel=channel,
                        status="pending",
                    )
                    session.add(prior)
                    deliveries.append(prior)
                elif prior.status != "delivered":
                    deliveries.append(prior)
        await session.commit()

        delivered = failed = 0
        for delivery in deliveries:
            user = await session.get(User, delivery.recipient_user_id)
            if user is None:
                delivery.status = "failed"
                delivery.error = "recipient no longer exists"
                failed += 1
                await session.commit()
                continue
            try:
                if delivery.channel == "sms":
                    result = await mcp_client.call_tool("notify_citizen_sms", {
                        "phone_number": user.phone,
                        "message": message,
                        "incident_id": incident.id,
                        "idempotency_key": delivery.id,
                    })
                else:
                    result = await mcp_client.call_tool("notify_citizen_email", {
                        "recipient_email": user.email,
                        "subject": f"Namma Civic incident update: {incident.title}",
                        "body": message,
                        "incident_id": incident.id,
                        "idempotency_key": delivery.id,
                    })
                delivery.status = "delivered" if str(result.get("status", "")).upper() in {"DELIVERED", "SENT", "QUEUED"} else "failed"
                delivery.provider_delivery_id = result.get("delivery_id") or result.get("message_id")
                delivery.error = None if delivery.status == "delivered" else "provider did not confirm delivery"
                delivery.sent_at = datetime.now(timezone.utc) if delivery.status == "delivered" else None
                delivered += delivery.status == "delivered"
                failed += delivery.status != "delivered"
            except Exception as exc:
                delivery.status = "failed"
                delivery.error = f"{type(exc).__name__}: delivery failed"
                failed += 1
            await session.commit()
        return {"recipient_count": len(recipients), "delivery_count": len(deliveries), "delivered_count": delivered, "failed_count": failed}

    @staticmethod
    async def change_status(
        session: AsyncSession,
        incident_id: str,
        status: IncidentStatus,
        *,
        actor_id: Optional[str],
        note: str,
    ) -> Dict[str, Any]:
        """Change incident status, append its public timeline, and notify reporters."""
        incident = await session.get(Incident, incident_id)
        if incident is None:
            raise ValueError("Incident not found")
        incident.status = status
        incident.resolved_at = datetime.now(timezone.utc) if status == IncidentStatus.resolved else None
        event = IncidentTimeline(
            incident_id=incident.id,
            actor_id=actor_id,
            event_type="status_changed",
            status=status.value,
            note=note,
        )
        session.add(event)
        await session.flush()
        await session.commit()
        message = f"Namma Civic incident {incident.id[:8]} is now {status.value}. {note}"
        return await IncidentFollowUpService.notify_reporters(
            session, incident, event_type="status_changed", message=message, event_key=event.id,
        )

    @staticmethod
    async def dispute_and_reopen(
        session: AsyncSession,
        incident_id: str,
        reporter_id: str,
        reason: str,
    ) -> Dict[str, str]:
        """Reopen only a resolved incident for a citizen with an active linked report."""
        incident = await session.get(Incident, incident_id)
        if incident is None:
            raise ValueError("Incident not found")
        owns_link = await session.scalar(
            select(ReportLink.id)
            .join(Complaint, Complaint.id == ReportLink.complaint_id)
            .where(
                ReportLink.incident_id == incident.id,
                ReportLink.is_active.is_(True),
                Complaint.citizen_id == reporter_id,
            )
        )
        if not owns_link:
            raise PermissionError("Only a linked reporter can dispute this incident")
        if incident.status != IncidentStatus.resolved:
            raise ValueError("Only a resolved incident can be reopened")
        incident.status = IncidentStatus.open
        incident.resolved_at = None
        event = IncidentTimeline(
            incident_id=incident.id,
            actor_id=reporter_id,
            event_type="reporter_dispute_reopened",
            status=incident.status.value,
            note=reason,
        )
        session.add(event)
        active_order = await session.scalar(select(WorkOrder).where(
            WorkOrder.incident_id == incident.id,
            WorkOrder.status.not_in((WorkOrderStatus.completed, WorkOrderStatus.cancelled)),
        ))
        if active_order is None:
            latest_order = await session.scalar(select(WorkOrder).where(
                WorkOrder.incident_id == incident.id,
            ).order_by(WorkOrder.created_at.desc()))
            session.add(WorkOrder(
                incident_id=incident.id,
                department_id=latest_order.department_id if latest_order else None,
                priority=incident.priority,
                status=WorkOrderStatus.queued,
            ))
        await session.flush()
        await session.commit()
        await IncidentFollowUpService.notify_reporters(
            session, incident, event_type="reopened",
            message=f"Incident {incident.id[:8]} was reopened after a reporter dispute. {reason}",
            event_key=event.id,
        )
        return {"incident_id": incident.id, "status": incident.status.value}


def _next_step(status: IncidentStatus) -> str:
    """Translate operational state into a short citizen-facing explanation."""
    return {
        IncidentStatus.open: "The report is awaiting department review and assignment.",
        IncidentStatus.in_progress: "A civic work order is active; the department is working on the issue.",
        IncidentStatus.resolved: "Resolution was recorded. A linked reporter can dispute it if the issue remains.",
        IncidentStatus.closed: "This incident is closed. Submit a new report if the problem returns.",
    }[status]


def _public_event_note(event_type: str, status: str) -> str:
    """Use fixed public descriptions instead of exposing free-text audit notes."""
    if event_type == "report_linked":
        return "A citizen report was linked to this incident."
    if event_type == "work_order_created":
        return "A municipal work order was created for this incident."
    if event_type == "resolution_verified":
        return "Resolution evidence was reviewed and the incident was marked resolved."
    if event_type == "reporter_dispute_reopened":
        return "A linked reporter disputed the resolution and the incident was reopened."
    if event_type == "sla_escalation":
        return "The incident was escalated for an SLA review."
    return f"Incident status is {status}."
