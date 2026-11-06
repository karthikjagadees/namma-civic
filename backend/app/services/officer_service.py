"""
Officer Command Center Service
Handles queue management, workload statistics, assignment, and rapid dispatch.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.mcp.client import mcp_client
from app.models.complaint import Complaint, ComplaintStatus, ComplaintTimeline, PriorityLevel
from app.models.department import Department
from app.models.report_link import ReportLink
from app.models.user import User
from app.services.sla_service import SLAService


class OfficerService:
    """Tactical command services for municipal field officers and department leads."""

    @staticmethod
    async def get_officer_queue(
        session: AsyncSession,
        officer_id: Optional[str] = None,
        department_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        priority_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve assigned complaints for an officer or their department with live SLA telemetry.
        """
        stmt = select(Complaint).options(
            selectinload(Complaint.media),
            selectinload(Complaint.timeline),
            selectinload(Complaint.ai_analysis)
        )

        # Dynamically resolve department_id if code (ROADS, WATER, etc.) or UUID is provided
        resolved_dept_id = None
        if department_id and department_id != "all":
            dept_res = await session.execute(
                select(Department.id).where(
                    or_(
                        Department.code == department_id.upper(),
                        Department.id == department_id,
                        func.lower(Department.name).contains(department_id.lower()),
                    )
                )
            )
            resolved_dept_id = dept_res.scalar_one_or_none() or department_id

        conditions = []
        if resolved_dept_id:
            # Department queues include unrouted reports for initial triage.
            # Explicit department filters omit officer_id and stay strictly scoped.
            department_conditions = [Complaint.department_id == resolved_dept_id]
            if officer_id:
                department_conditions.extend([
                    Complaint.assigned_officer_id == officer_id,
                    Complaint.department_id.is_(None),
                ])
            conditions.append(or_(*department_conditions))
        elif officer_id and department_id != "all":
            # Default view: cases in officer's department or assigned to officer or unassigned
            conditions.append(or_(Complaint.assigned_officer_id == officer_id, Complaint.assigned_officer_id.is_(None)))

        if status_filter:
            try:
                conditions.append(Complaint.status == ComplaintStatus(status_filter))
            except ValueError:
                pass

        if priority_filter:
            try:
                conditions.append(Complaint.priority == PriorityLevel(priority_filter))
            except ValueError:
                pass

        if conditions:
            stmt = stmt.where(*conditions)

        stmt = stmt.order_by(Complaint.created_at.desc()).offset(offset).limit(limit)
        res = await session.execute(stmt)
        complaints = res.scalars().all()

        # If empty and no explicit filters, show recent platform complaints for dispatch triage
        if not complaints and not status_filter and not priority_filter and not department_id:
            fallback_stmt = select(Complaint).options(
                selectinload(Complaint.media),
                selectinload(Complaint.timeline),
                selectinload(Complaint.ai_analysis)
            ).order_by(Complaint.created_at.desc()).limit(limit)
            fallback_res = await session.execute(fallback_stmt)
            complaints = fallback_res.scalars().all()

        # The queue is incident-oriented: preserve all report rows in storage,
        # but display only the newest linked report as the incident card.
        complaint_ids = [complaint.id for complaint in complaints]
        active_links = []
        if complaint_ids:
            active_links = list((await session.scalars(
                select(ReportLink).where(
                    ReportLink.complaint_id.in_(complaint_ids),
                    ReportLink.is_active.is_(True),
                )
            )).all())
        incident_by_complaint = {link.complaint_id: link.incident_id for link in active_links}
        incident_ids = set(incident_by_complaint.values())
        counts_by_incident: dict[str, tuple[int, int]] = {}
        if incident_ids:
            count_rows = await session.execute(
                select(
                    ReportLink.incident_id,
                    func.count(func.distinct(Complaint.id)),
                    func.count(func.distinct(Complaint.citizen_id)),
                )
                .join(Complaint, Complaint.id == ReportLink.complaint_id)
                .where(
                    ReportLink.incident_id.in_(incident_ids),
                    ReportLink.is_active.is_(True),
                )
                .group_by(ReportLink.incident_id)
            )
            counts_by_incident = {
                incident_id: (int(report_count), int(reporter_count))
                for incident_id, report_count, reporter_count in count_rows
            }

        grouped_complaints = []
        seen_incidents: set[str] = set()
        for complaint in complaints:
            incident_id = incident_by_complaint.get(complaint.id)
            if incident_id and incident_id in seen_incidents:
                continue
            if incident_id:
                seen_incidents.add(incident_id)
            grouped_complaints.append(complaint)

        # Fetch department names mapping
        dept_ids = {c.department_id for c in complaints if c.department_id}
        dept_map = {}
        if dept_ids:
            dept_res = await session.execute(select(Department).where(Department.id.in_(dept_ids)))
            dept_map = {str(d.id): d.name for d in dept_res.scalars().all()}

        output = []
        for c in grouped_complaints:
            incident_id = incident_by_complaint.get(c.id)
            report_count, reporter_count = counts_by_incident.get(incident_id, (1, 1)) if incident_id else (1, 1)
            sla = SLAService.calculate_sla(c)
            images = [
                m.file_url
                for m in c.media
                if getattr(m.media_type, "value", m.media_type) == "image"
            ] if c.media else []

            output.append({
                "id": str(c.id),
                "incident_id": incident_id,
                "report_count": report_count,
                "reporter_count": reporter_count,
                "tracking_id": c.tracking_id,
                "title": c.title,
                "description": c.description,
                "status": getattr(c.status, "value", c.status),
                "priority": getattr(c.priority, "value", c.priority) if c.priority else "MEDIUM",
                "category": getattr(c.category, "value", c.category) if c.category else "general",
                "address": c.address or "Municipal Ward Zone",
                "latitude": c.latitude,
                "longitude": c.longitude,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "department_id": str(c.department_id) if c.department_id else None,
                "department_name": dept_map.get(str(c.department_id), "General Public Works") if c.department_id else "General Public Works",
                "assigned_officer_id": c.assigned_officer_id,
                "media": [
                    {
                        "file_url": m.file_url,
                        "media_type": getattr(m.media_type, "value", m.media_type),
                    }
                    for m in c.media
                ] if c.media else [],
                "images": images,
                "sla": {
                    "deadline": sla["deadline"].isoformat() if hasattr(sla.get("deadline"), "isoformat") else (str(sla.get("deadline")) if sla.get("deadline") else None),
                    "hours_remaining": sla.get("hours_remaining", 0),
                    "percent_consumed": sla.get("percent_consumed", 0),
                    "sla_status": sla.get("sla_status", "ON_TRACK"),
                    "is_breached": sla.get("is_breached", False),
                }
            })

        return output

    @staticmethod
    async def get_officer_roster(session: AsyncSession) -> List[Dict[str, Any]]:
        """Retrieve all active municipal officers with their departments."""
        from app.models.user import UserRole
        stmt = (
            select(User)
            .where(User.role == UserRole.officer, User.is_active == True)
            .order_by(User.full_name)
        )
        res = await session.execute(stmt)
        officers = res.scalars().all()

        dept_res = await session.execute(select(Department))
        dept_map = {str(d.id): d.name for d in dept_res.scalars().all()}

        return [
            {
                "id": str(u.id),
                "full_name": u.full_name,
                "email": u.email,
                "department_id": str(u.department_id) if u.department_id else None,
                "department_name": dept_map.get(str(u.department_id), "General Public Works") if u.department_id else "General Public Works",
            }
            for u in officers
        ]

    @staticmethod
    async def get_officer_workload_stats(
        session: AsyncSession,
        officer_id: Optional[str] = None,
        department_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculate live workload metrics, SLA compliance rate, and risk caseload."""
        stmt = select(Complaint)
        if department_id:
            stmt = stmt.where(or_(Complaint.assigned_officer_id == officer_id, Complaint.department_id == department_id))
        elif officer_id:
            stmt = stmt.where(Complaint.assigned_officer_id == officer_id)

        res = await session.execute(stmt)
        complaints = res.scalars().all()

        total = len(complaints)
        active = 0
        resolved = 0
        breached = 0
        at_risk = 0

        for c in complaints:
            if c.status == ComplaintStatus.resolved:
                resolved += 1
            else:
                active += 1
                sla = SLAService.calculate_sla(c)
                if sla["sla_status"] == "BREACHED":
                    breached += 1
                elif sla["sla_status"] == "AT_RISK":
                    at_risk += 1

        compliance = round(((total - breached) / max(1, total)) * 100, 1)

        return {
            "total_cases": total,
            "active_cases": active,
            "resolved_cases": resolved,
            "at_risk_cases": at_risk,
            "breached_cases": breached,
            "compliance_rate": compliance,
            "duty_shift": "ALPHA_ACTIVE",
            "telemetry_time": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    async def assign_complaint(
        session: AsyncSession,
        complaint_id: str,
        officer_id: str,
        reason: Optional[str] = None,
        force_override: bool = False,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assign or forcefully reassign an incident to a specific officer and sync department."""
        try:
            cid = uuid.UUID(complaint_id)
        except ValueError:
            raise ValueError("Invalid complaint UUID format")

        stmt = select(Complaint).where(Complaint.id == str(cid)).options(selectinload(Complaint.timeline))
        res = await session.execute(stmt)
        complaint = res.scalar_one_or_none()
        if not complaint:
            raise ValueError("Complaint not found")

        # Resolve target officer
        officer_res = await session.execute(select(User).where(User.id == officer_id))
        target_officer = officer_res.scalar_one_or_none()
        officer_name = target_officer.full_name if target_officer else f"Officer #{officer_id[:8].upper()}"

        complaint.assigned_officer_id = officer_id
        dept_name = "General"
        if target_officer and target_officer.department_id:
            complaint.department_id = target_officer.department_id
            dept_res = await session.execute(select(Department).where(Department.id == target_officer.department_id))
            dept_obj = dept_res.scalar_one_or_none()
            if dept_obj:
                dept_name = dept_obj.name

        if complaint.status == ComplaintStatus.pending:
            complaint.status = ComplaintStatus.assigned

        if force_override:
            reason_str = reason or "Duty officer neglected duty / SLA escalation"
            directives_str = f" Directives: {notes}" if notes else " Directives: Immediate field intervention required."
            note = f"🚨 FORCED REASSIGNMENT: Transferred to {officer_name} ({dept_name}). Reason: {reason_str}.{directives_str}"
        else:
            reason_str = f" Reason: {reason}." if reason else ""
            notes_str = f" Directives: {notes}" if notes else ""
            note = f"Assigned to {officer_name} ({dept_name}).{reason_str}{notes_str}".strip()

        session.add(ComplaintTimeline(complaint_id=complaint.id, status=complaint.status, note=note))
        await session.commit()

        return {
            "complaint_id": str(complaint.id),
            "assigned_officer_id": officer_id,
            "assigned_officer_name": officer_name,
            "department_id": str(complaint.department_id) if complaint.department_id else None,
            "status": complaint.status.value,
        }

    @staticmethod
    async def quick_crew_dispatch(
        session: AsyncSession,
        complaint_id: str,
        crew_id: str,
        department_code: str,
        priority: str = "HIGH",
        instructions: str = "",
    ) -> Dict[str, Any]:
        """Dispatch field maintenance crew via MCP Tool Server and record work order in timeline."""
        try:
            cid = uuid.UUID(complaint_id)
        except ValueError:
            raise ValueError("Invalid complaint UUID format")

        stmt = select(Complaint).where(Complaint.id == str(cid)).options(selectinload(Complaint.timeline))
        res = await session.execute(stmt)
        complaint = res.scalar_one_or_none()
        if not complaint:
            raise ValueError("Complaint not found")

        # Execute MCP Tool
        mcp_res = await mcp_client.call_tool("civic_work_order_dispatch", {
            "complaint_id": str(complaint.id),
            "crew_id": crew_id,
            "department_code": department_code,
            "priority": priority,
        })

        wo_id = mcp_res.get("work_order_id", f"WO-{uuid.uuid4().hex[:8].upper()}")
        complaint.status = ComplaintStatus.in_progress

        timeline_note = (
            f"🚀 Officer Tactical Crew Dispatch: Work Order {wo_id} assigned to crew {crew_id} ({department_code}). "
            f"Instructions: {instructions or 'Standard municipal remediation protocol'}"
        )
        session.add(ComplaintTimeline(complaint_id=complaint.id, status=complaint.status, note=timeline_note))
        await session.commit()

        # Trigger crew dispatch email notice to citizen
        try:
            import asyncio
            from app.models.user import User
            from app.services.email_service import EmailService
            user_res = await session.execute(select(User).where(User.id == complaint.citizen_id))
            citizen = user_res.scalar_one_or_none()
            if citizen and citizen.email:
                asyncio.create_task(
                    EmailService.send_crew_dispatch_notice(
                        complaint=complaint,
                        citizen_email=citizen.email,
                        crew_id=crew_id,
                        work_order_id=wo_id,
                        instructions=instructions,
                    )
                )
        except Exception as e:
            pass

        return {
            "work_order_id": wo_id,
            "status": "DISPATCHED",
            "complaint_id": str(complaint.id),
            "assigned_crew": crew_id,
            "mcp_telemetry": mcp_res,
        }
