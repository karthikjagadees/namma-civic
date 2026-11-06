"""Officer duplicate-review queue, audited decisions, and operational metrics."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint, ComplaintMedia, ComplaintStatus, MediaType, PriorityLevel
from app.models.duplicate_review import DuplicateReviewCase, DuplicateReviewDecision
from app.models.follow_up import IncidentTimeline
from app.models.incident import Incident, IncidentStatus
from app.models.report_link import ReportLink
from app.models.user import User, UserRole
from app.models.work_order import WorkOrder, WorkOrderStatus
from app.services.incident_service import create_recurrence_incident_for_report, reassign_report_link


class DuplicateReviewService:
    """Persist uncertain matches and make officer decisions auditable labels."""

    @staticmethod
    async def enqueue(
        session: AsyncSession,
        complaint_id: str,
        *,
        reason: str,
        candidates: list[dict[str, Any]],
        failures: list[str] | None = None,
    ) -> DuplicateReviewCase:
        """Create or refresh the single review case associated with a complaint."""
        case = await session.scalar(select(DuplicateReviewCase).where(
            DuplicateReviewCase.complaint_id == complaint_id,
        ).with_for_update())
        if case is None:
            case = DuplicateReviewCase(
                complaint_id=complaint_id, status="pending", reason=reason,
                candidates=candidates, failures=failures or [],
            )
            session.add(case)
        elif case.status == "pending":
            case.reason = reason
            case.candidates = candidates
            case.failures = failures or []
        await session.flush()
        return case

    @staticmethod
    async def list_queue(session: AsyncSession, limit: int = 100) -> list[dict[str, Any]]:
        """Return pending reports beside candidate incident evidence for officers."""
        cases = list((await session.scalars(
            select(DuplicateReviewCase)
            .where(DuplicateReviewCase.status == "pending")
            .order_by(DuplicateReviewCase.created_at, DuplicateReviewCase.id)
            .limit(limit)
        )).all())
        result = []
        for case in cases:
            report = await session.get(Complaint, case.complaint_id)
            if report is None:
                continue
            report_media = await _photos(session, report.id)
            candidates = []
            for snapshot in case.candidates:
                incident = await session.get(Incident, snapshot.get("incident_id"))
                if incident is None:
                    continue
                linked_reports = list((await session.scalars(
                    select(Complaint)
                    .join(ReportLink, ReportLink.complaint_id == Complaint.id)
                    .where(ReportLink.incident_id == incident.id, ReportLink.is_active.is_(True))
                    .order_by(Complaint.created_at, Complaint.id)
                    .limit(5)
                )).all())
                sample_reports = []
                for linked_report in linked_reports:
                    sample_reports.append({
                        "complaint_id": linked_report.id,
                        "title": linked_report.title,
                        "description": linked_report.description,
                        "channel": linked_report.source.value,
                        "photos": await _photos(session, linked_report.id),
                    })
                candidates.append({
                    **snapshot,
                    "incident_id": incident.id,
                    "title": incident.title,
                    "category": incident.category.value,
                    "status": incident.status.value,
                    "location": {"latitude": incident.latitude, "longitude": incident.longitude,
                                 "address": incident.address, "landmark": incident.landmark},
                    "photos": [photo for row in sample_reports for photo in row["photos"]],
                    "reports": sample_reports,
                })
            result.append({
                "review_id": case.id,
                "complaint_id": report.id,
                "status": case.status,
                "reason": case.reason,
                "failures": list(case.failures or []),
                "created_at": case.created_at.isoformat(),
                "report": {
                    "complaint_id": report.id,
                    "title": report.title,
                    "description": report.description,
                    "category": report.category.value,
                    "channel": report.source.value,
                    "location": {"latitude": report.latitude, "longitude": report.longitude,
                                 "address": report.address, "landmark": report.landmark},
                    "photos": report_media,
                },
                "candidates": candidates,
            })
        return result

    @staticmethod
    async def decide(
        session: AsyncSession,
        review_id: str,
        officer_id: str,
        *,
        action: str,
        candidate_incident_id: Optional[str],
        note: str,
    ) -> dict[str, str]:
        """Resolve a review action, preserve link history, and save its label."""
        allowed = {"confirm_link", "reject_match", "merge_incidents", "split_report"}
        if action not in allowed:
            raise ValueError("Unsupported duplicate review action")
        case = await session.scalar(select(DuplicateReviewCase).where(
            DuplicateReviewCase.id == review_id,
        ).with_for_update())
        if case is None:
            raise LookupError("Duplicate review case was not found")
        if case.status != "pending":
            raise ValueError("Duplicate review case is already resolved")
        officer = await session.get(User, officer_id)
        if officer is None or officer.role not in (UserRole.officer, UserRole.admin):
            raise PermissionError("Officer privileges are required")
        report = await session.get(Complaint, case.complaint_id)
        if report is None:
            raise LookupError("Reviewed complaint was not found")
        snapshot = next((candidate for candidate in case.candidates
                         if candidate.get("incident_id") == candidate_incident_id), None)
        if action != "split_report" and snapshot is None:
            raise ValueError("Selected candidate is not part of this review")
        if action == "split_report" and candidate_incident_id and snapshot is None:
            raise ValueError("Selected candidate is not part of this review")

        active_link = await session.scalar(select(ReportLink).where(
            ReportLink.complaint_id == report.id, ReportLink.is_active.is_(True),
        ).with_for_update())
        if active_link is None:
            raise ValueError("Reviewed complaint has no active incident link")
        source_incident_id = active_link.incident_id
        is_duplicate = action in {"confirm_link", "merge_incidents"}
        resulting_incident_id = source_incident_id
        if action == "confirm_link":
            candidate_incident = await session.get(Incident, candidate_incident_id)
            if candidate_incident is None:
                raise LookupError("Candidate incident was not found")
            if candidate_incident.status == IncidentStatus.resolved:
                recurrence, _ = await create_recurrence_incident_for_report(
                    session, report, candidate_incident.id,
                    float(snapshot.get("score") or 0.0),
                    {**snapshot, "decision": "officer_confirmed_recurrence"},
                )
                resulting_incident_id = recurrence.id
                await _consolidate_work_orders(session, source_incident_id, recurrence.id)
                await session.flush()
                active_recurrence_order = await session.scalar(select(WorkOrder).where(
                    WorkOrder.incident_id == recurrence.id,
                    WorkOrder.status.not_in((WorkOrderStatus.completed, WorkOrderStatus.cancelled)),
                ))
                if active_recurrence_order is None:
                    session.add(WorkOrder(
                        incident_id=recurrence.id, status=WorkOrderStatus.queued,
                        priority=recurrence.priority or "medium",
                    ))
            else:
                await _move_one_report(session, active_link, candidate_incident_id, officer_id, note, snapshot)
                resulting_incident_id = candidate_incident_id
                await _consolidate_work_orders(session, source_incident_id, candidate_incident_id)
        elif action == "merge_incidents":
            await _merge_incidents(session, source_incident_id, candidate_incident_id, officer_id, note)
            resulting_incident_id = candidate_incident_id
        elif action == "split_report":
            new_incident = await _split_report(session, report, active_link, officer_id, note, snapshot)
        elif action == "reject_match":
            source_incident = await session.get(Incident, source_incident_id)
            report.status = ComplaintStatus.assigned
            if source_incident is not None and source_incident.status == IncidentStatus.open:
                source_incident.status = IncidentStatus.in_progress
            existing_order = await session.scalar(select(WorkOrder).where(
                WorkOrder.incident_id == source_incident_id,
                WorkOrder.status.not_in((WorkOrderStatus.completed, WorkOrderStatus.cancelled)),
            ))
            if existing_order is None:
                session.add(WorkOrder(
                    incident_id=source_incident_id,
                    department_id=report.department_id,
                    status=WorkOrderStatus.queued,
                    priority=report.priority.value if hasattr(report.priority, "value") else str(report.priority),
                ))
        else:
            new_incident = None

        case.status = "resolved"
        case.resolution_action = action
        case.resolved_by_id = officer_id
        case.updated_at = datetime.now(timezone.utc)
        decision = DuplicateReviewDecision(
            review_case_id=case.id,
            complaint_id=report.id,
            candidate_incident_id=candidate_incident_id,
            officer_id=officer_id,
            action=action,
            is_duplicate=is_duplicate,
            score=snapshot.get("score") if snapshot else None,
            evidence=snapshot or {"reason": case.reason, "failures": case.failures},
            note=note,
        )
        session.add(decision)
        audit_incident_id = resulting_incident_id if is_duplicate else (new_incident.id if action == "split_report" else source_incident_id)
        session.add(IncidentTimeline(
            incident_id=audit_incident_id,
            actor_id=officer_id,
            event_type=f"duplicate_review_{action}",
            status="reviewed",
            note=f"Officer reviewed report {report.id} ({action}). {note}".strip(),
        ))
        await session.commit()
        response = {"review_id": case.id, "status": case.status, "action": action}
        if action in {"confirm_link", "merge_incidents"}:
            response["incident_id"] = resulting_incident_id
        if action == "split_report":
            response["new_incident_id"] = new_incident.id
        return response

    @staticmethod
    async def analytics(session: AsyncSession) -> dict[str, Any]:
        """Compute review and duplicate operations metrics from persisted data."""
        grouped = (await session.execute(
            select(ReportLink.incident_id, func.count(ReportLink.id))
            .where(ReportLink.is_active.is_(True))
            .group_by(ReportLink.incident_id)
        )).all()
        order_groups = (await session.execute(
            select(WorkOrder.incident_id, func.count(WorkOrder.id))
            .where(WorkOrder.status.not_in((WorkOrderStatus.completed, WorkOrderStatus.cancelled)))
            .group_by(WorkOrder.incident_id)
        )).all()
        reports_by_incident = {incident_id: int(count) for incident_id, count in grouped}
        orders_by_incident = {incident_id: int(count) for incident_id, count in order_groups}
        duplicates_linked = sum(max(0, count - 1) for count in reports_by_incident.values())
        avoided = sum(
            min(count - 1, max(0, count - orders_by_incident.get(incident_id, 0)))
            for incident_id, count in reports_by_incident.items()
            if count > 1 and orders_by_incident.get(incident_id, 0) > 0
        )
        pending = int(await session.scalar(select(func.count(DuplicateReviewCase.id)).where(
            DuplicateReviewCase.status == "pending",
        )) or 0)
        decisions = list((await session.scalars(
            select(DuplicateReviewDecision).where(DuplicateReviewDecision.candidate_incident_id.is_not(None))
            .order_by(DuplicateReviewDecision.created_at.desc(), DuplicateReviewDecision.id.desc())
        )).all())
        latest: dict[tuple[str, str, str], bool] = {}
        for row in decisions:
            latest.setdefault((row.complaint_id, row.candidate_incident_id, row.officer_id), row.is_duplicate)
        pair_votes: dict[tuple[str, str], list[bool]] = {}
        for (complaint_id, candidate_id, _officer_id), label in latest.items():
            pair_votes.setdefault((complaint_id, candidate_id), []).append(label)
        eligible_votes = [votes for votes in pair_votes.values() if len(votes) >= 2]
        total_votes = sum(map(len, eligible_votes))
        agreement_rate = (
            sum(max(sum(votes), len(votes) - sum(votes)) for votes in eligible_votes) / total_votes
            if total_votes else None
        )
        return {
            "duplicates_linked": duplicates_linked,
            "work_orders_avoided": avoided,
            "review_queue_volume": pending,
            "officer_agreement_rate": agreement_rate,
            "agreement_pair_count": len(eligible_votes),
        }


async def _photos(session: AsyncSession, complaint_id: str) -> list[dict[str, Any]]:
    """Return photo references and hash signals without loading binary contents."""
    rows = list((await session.scalars(select(ComplaintMedia).where(
        ComplaintMedia.complaint_id == complaint_id,
        ComplaintMedia.media_type == MediaType.image,
    ).order_by(ComplaintMedia.created_at))).all())
    return [{"url": row.file_url, "file_name": row.file_name, "perceptual_hash": row.perceptual_hash} for row in rows]


async def _move_one_report(
    session: AsyncSession,
    link: ReportLink,
    target_id: str,
    officer_id: str,
    note: str,
    snapshot: dict[str, Any],
) -> None:
    """Create the officer's new active version of one report link."""
    if link.incident_id != target_id:
        await reassign_report_link(
            session, link.id, target_id, officer_id, note,
            match_score=snapshot.get("score"), signal_evidence=snapshot,
        )


async def _consolidate_work_orders(session: AsyncSession, source_id: str, target_id: str) -> None:
    """Keep one active work order after an officer links incidents."""
    if source_id == target_id:
        return
    active_statuses = (WorkOrderStatus.completed, WorkOrderStatus.cancelled)
    source = await session.scalar(select(WorkOrder).where(
        WorkOrder.incident_id == source_id, WorkOrder.status.not_in(active_statuses),
    ).with_for_update())
    target = await session.scalar(select(WorkOrder).where(
        WorkOrder.incident_id == target_id, WorkOrder.status.not_in(active_statuses),
    ).with_for_update())
    if source is not None:
        if target is None:
            source.incident_id = target_id
        else:
            source.status = WorkOrderStatus.cancelled
            source.closed_at = datetime.now(timezone.utc)


async def _merge_incidents(
    session: AsyncSession, source_id: str, target_id: str, officer_id: str, note: str,
) -> None:
    """Move every source report link to the target and retain source history."""
    if source_id == target_id:
        raise ValueError("Cannot merge an incident into itself")
    source = await session.get(Incident, source_id)
    target = await session.get(Incident, target_id)
    if source is None or target is None:
        raise LookupError("Source or target incident was not found")
    if target.status == IncidentStatus.resolved:
        raise ValueError("A resolved incident cannot be merged into; create a recurrence incident instead")
    source_links = list((await session.scalars(select(ReportLink).where(
        ReportLink.incident_id == source_id, ReportLink.is_active.is_(True),
    ).with_for_update())).all())
    for link in source_links:
        await reassign_report_link(session, link.id, target_id, officer_id, note,
                                   match_score=link.match_score, signal_evidence=link.signal_evidence)
    await _consolidate_work_orders(session, source_id, target_id)
    source.status = IncidentStatus.closed
    source.resolved_at = datetime.now(timezone.utc)
    source.updated_at = datetime.now(timezone.utc)
    session.add_all([
        IncidentTimeline(incident_id=source_id, actor_id=officer_id, event_type="incident_merged", status="closed",
                        note=f"Merged into incident {target_id}. {note}"),
        IncidentTimeline(incident_id=target_id, actor_id=officer_id, event_type="incident_merge_received", status=target.status.value,
                        note=f"Incident {source_id} was merged into this incident. {note}"),
    ])


async def _split_report(
    session: AsyncSession,
    report: Complaint,
    old_link: ReportLink,
    officer_id: str,
    note: str,
    snapshot: dict[str, Any] | None,
) -> Incident:
    """Give a report its own incident and queued order without editing evidence."""
    incident = Incident(
        title=report.title, category=report.category, status=IncidentStatus.open,
        priority=report.priority.value if hasattr(report.priority, "value") else str(report.priority),
        latitude=report.latitude, longitude=report.longitude, address=report.address, landmark=report.landmark,
        location_confidence=report.location_confidence, location_accuracy_m=report.location_accuracy_m,
    )
    session.add(incident)
    await session.flush()
    await reassign_report_link(
        session, old_link.id, incident.id, officer_id, note,
        match_score=old_link.match_score,
        signal_evidence={**(snapshot or {}), "decision": "officer_split"},
    )
    session.add(WorkOrder(
        incident_id=incident.id, department_id=report.department_id,
        status=WorkOrderStatus.queued,
        priority=incident.priority or PriorityLevel.medium.value,
    ))
    return incident
