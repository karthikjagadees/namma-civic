"""Persist incident links and idempotent work orders before dispatching actions."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.agents.state import CivicActionState
from app.core.database import async_session_factory
from app.deduplication.engine import MatchDecision, MatchResult, ReportEvidence
from app.deduplication.repository import resolve_report_against_incidents
from app.models.complaint import Complaint, ComplaintStatus, ComplaintTimeline, PriorityLevel
from app.models.incident import Incident, IncidentStatus
from app.models.follow_up import IncidentTimeline
from app.models.report_link import ReportLink, ReportLinkDecisionSource
from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderStatus
from app.services.incident_service import create_recurrence_incident_for_report

logger = logging.getLogger("namma-civic.agent.action")


async def action_node(state: CivicActionState) -> Dict[str, Any]:
    """Apply the resolver outcome, maintain one active order, then notify the reporter."""
    complaint_id = state.get("complaint_id")
    routing = state.get("routing_result", {})
    dedup = state.get("deduplication_result", {})
    decision = "recurrence" if dedup.get("recurrence_of_incident_id") else dedup.get("decision", "new_incident")
    human_decision = state.get("human_decision") or {}
    rejected = human_decision.get("approved") is False
    dept_name = routing.get("department_name", "Public Works")
    priority = str(routing.get("priority", "medium")).lower()
    sla_hours = routing.get("sla_hours", 48)
    work_order: WorkOrder | None = None
    persisted_incident_id: str | None = None
    linked = decision == "auto_link"
    reporter_user_id: str | None = None
    link_event_id: str | None = None
    status_event_id: str | None = None
    status_changed = False

    try:
        async with async_session_factory() as session:
            # A stable row update acts as a database-wide intake mutex: it is a
            # SQLite write lock locally and a row lock in PostgreSQL. Re-score
            # after acquiring it so two concurrent arrivals cannot both rely on
            # a stale "new incident" decision.
            await session.execute(
                update(Incident)
                .where(Incident.id == select(Incident.id).order_by(Incident.id).limit(1).scalar_subquery())
                .values(updated_at=Incident.updated_at)
            )
            complaint = await session.scalar(
                select(Complaint).where(Complaint.id == complaint_id)
                .options(selectinload(Complaint.media))
                .with_for_update()
            )
            if complaint is None:
                raise ValueError(f"Complaint {complaint_id} was not found")

            evidence = ReportEvidence(
                report_id=complaint.id,
                text=f"{complaint.title}\n{complaint.description}",
                category=complaint.category.value,
                latitude=complaint.latitude,
                longitude=complaint.longitude,
                location_confidence=complaint.location_confidence,
                location_accuracy_m=complaint.location_accuracy_m,
                address=complaint.address,
                landmark=complaint.landmark,
                photo_hashes=tuple(
                    media.perceptual_hash for media in complaint.media
                    if media.media_type.value == "image" and media.perceptual_hash
                ),
                channel=complaint.source.value,
                reported_at=complaint.created_at,
            )
            latest_match = await resolve_report_against_incidents(session, evidence)
            if latest_match.failures:
                latest_match = MatchResult(
                    MatchDecision.officer_review,
                    candidate_scores=latest_match.candidate_scores,
                    reasons=latest_match.reasons,
                    failures=latest_match.failures,
                )
            dedup = {
                "decision": latest_match.decision.value,
                "incident_id": latest_match.incident_id,
                "recurrence_of_incident_id": latest_match.recurrence_of_incident_id,
                "best_score": latest_match.best_score,
                "ranked_candidates": [
                    {"incident_id": candidate.incident_id, "score": candidate.fused_score,
                     "distance_m": candidate.distance_m, "signals": dict(candidate.signals)}
                    for candidate in latest_match.candidate_scores
                ],
                "reasons": list(latest_match.reasons),
                "failures": list(latest_match.failures),
            }
            decision = "recurrence" if latest_match.recurrence_of_incident_id else latest_match.decision.value
            linked = decision == "auto_link"
            if decision == "officer_review":
                from app.services.duplicate_review_service import DuplicateReviewService

                await DuplicateReviewService.enqueue(
                    session,
                    complaint.id,
                    reason=" ".join(latest_match.reasons) or "Duplicate match requires an officer decision.",
                    candidates=[
                        {
                            "incident_id": candidate.incident_id,
                            "score": candidate.fused_score,
                            "distance_m": candidate.distance_m,
                            "signals": dict(candidate.signals),
                        }
                        for candidate in latest_match.candidate_scores
                    ],
                    failures=list(latest_match.failures),
                )

            link = await session.scalar(
                select(ReportLink)
                .where(ReportLink.complaint_id == complaint.id, ReportLink.is_active.is_(True))
                .with_for_update()
            )
            if link is None:
                raise ValueError(f"Complaint {complaint.id} has no active incident link")
            source_incident_id = link.incident_id

            target_id = dedup.get("recurrence_of_incident_id") or dedup.get("incident_id")
            if linked and target_id and target_id != link.incident_id:
                target = await session.get(Incident, target_id)
                if target is None:
                    raise ValueError(f"Matched incident {target_id} was not found")
                prior_id = link.id
                link.is_active = False
                link.ended_at = datetime.now(timezone.utc)
                await session.flush()
                link = ReportLink(
                    complaint_id=complaint.id,
                    incident_id=target.id,
                    match_score=dedup.get("best_score"),
                    signal_evidence={
                        "decision": "auto_link",
                        "ranked_candidates": dedup.get("ranked_candidates", []),
                    },
                    decision_source=ReportLinkDecisionSource.auto,
                    supersedes_link_id=prior_id,
                )
                session.add(link)
                await session.flush()
            elif decision == "recurrence" and target_id and target_id != link.incident_id:
                signal_evidence = {
                    "decision": "recurrence",
                    "ranked_candidates": dedup.get("ranked_candidates", []),
                }
                incident, link = await create_recurrence_incident_for_report(
                    session=session,
                    complaint=complaint,
                    resolved_incident_id=target_id,
                    match_score=dedup.get("best_score") or 0.0,
                    signal_evidence=signal_evidence,
                )
                link.incident_id = incident.id

            incident = await session.get(Incident, link.incident_id)
            if incident is None:
                raise ValueError(f"Incident {link.incident_id} was not found")
            prior_incident_status = incident.status
            priority_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            if priority_rank.get(priority, 1) > priority_rank.get(incident.priority, 1):
                incident.priority = priority

            if linked and source_incident_id != incident.id:
                # A provisional one-report incident may already have dispatched
                # before a later report proves it belongs to this shared issue.
                # Move its existing order onto the canonical incident when safe;
                # otherwise cancel the redundant local order record.
                source_order = await session.scalar(
                    select(WorkOrder).where(
                        WorkOrder.incident_id == source_incident_id,
                        WorkOrder.status.not_in((WorkOrderStatus.completed, WorkOrderStatus.cancelled)),
                    ).with_for_update()
                )
                target_order = await session.scalar(
                    select(WorkOrder).where(
                        WorkOrder.incident_id == incident.id,
                        WorkOrder.status.not_in((WorkOrderStatus.completed, WorkOrderStatus.cancelled)),
                    ).with_for_update()
                )
                if source_order is not None:
                    if target_order is None:
                        source_order.incident_id = incident.id
                        source_order.priority = priority
                    else:
                        source_order.status = WorkOrderStatus.cancelled
                        source_order.closed_at = datetime.now(timezone.utc)
                # Completed/cancelled source orders are historical records too;
                # keep them attached to the canonical incident before removal.
                await session.execute(
                    update(WorkOrder)
                    .where(WorkOrder.incident_id == source_incident_id)
                    .values(incident_id=incident.id)
                )

                # Intake creates a provisional incident before the resolver
                # runs. Once its only active report moves, fold that shell
                # into the canonical incident so one physical issue has one
                # incident row. Preserve the old ID in each historical link's
                # evidence before moving the references.
                source_incident = await session.get(Incident, source_incident_id)
                other_active_link = await session.scalar(select(ReportLink.id).where(
                    ReportLink.incident_id == source_incident_id,
                    ReportLink.is_active.is_(True),
                ).limit(1))
                has_recurrence_child = await session.scalar(select(Incident.id).where(
                    Incident.recurrence_of_incident_id == source_incident_id,
                ).limit(1))
                if source_incident is not None and other_active_link is None and not has_recurrence_child:
                    historical_links = list((await session.scalars(select(ReportLink).where(
                        ReportLink.incident_id == source_incident_id,
                    ))).all())
                    for historical_link in historical_links:
                        evidence = dict(historical_link.signal_evidence or {})
                        evidence["retired_provisional_incident_id"] = source_incident_id
                        historical_link.signal_evidence = evidence
                        historical_link.incident = incident
                    await session.execute(
                        update(IncidentTimeline)
                        .where(IncidentTimeline.incident_id == source_incident_id)
                        .values(incident_id=incident.id)
                    )
                    await session.flush()
                    await session.delete(source_incident)

            if rejected:
                complaint.status = ComplaintStatus.rejected
                note = f"Report rejected by officer review. {human_decision.get('officer_notes', '')}".strip()
            elif decision == "officer_review":
                complaint.status = ComplaintStatus.verified
                note = "Report held for officer review of a possible duplicate; no new work order was dispatched."
            else:
                complaint.status = ComplaintStatus.assigned
                if routing.get("department_id"):
                    complaint.department_id = routing["department_id"]
                try:
                    complaint.priority = PriorityLevel(priority)
                except ValueError:
                    complaint.priority = PriorityLevel.medium
                complaint.severity = routing.get("severity", complaint.severity)

                active_order = await session.scalar(
                    select(WorkOrder)
                    .where(WorkOrder.incident_id == incident.id)
                    .order_by(WorkOrder.created_at)
                    .with_for_update()
                )
                # A duplicate is attached to the incident and its existing order.
                # It never creates another order if the incident has no active order.
                may_create_order = decision in ("new_incident", "recurrence")
                if active_order is not None and decision != "officer_review":
                    work_order = active_order
                    if priority_rank.get(priority, 1) > priority_rank.get(active_order.priority, 1):
                        active_order.priority = priority
                elif may_create_order:
                    work_order = WorkOrder(
                        incident_id=incident.id,
                        department_id=routing.get("department_id"),
                        status=WorkOrderStatus.queued,
                        priority=priority,
                    )
                    session.add(work_order)
                    await session.flush()
                elif active_order is None and decision == "auto_link":
                    # A provisional incident may have been created at report
                    # intake but not yet operationalized. The first action run
                    # may create its one order; later linked reports reuse it.
                    prior_order = await session.scalar(
                        select(WorkOrder.id).where(WorkOrder.incident_id == incident.id)
                    )
                    if prior_order is None:
                        work_order = WorkOrder(
                            incident_id=incident.id,
                            department_id=routing.get("department_id"),
                            status=WorkOrderStatus.queued,
                            priority=priority,
                        )
                        session.add(work_order)
                        await session.flush()
                if work_order is not None and incident.status == IncidentStatus.open:
                    incident.status = IncidentStatus.in_progress
                status_changed = incident.status != prior_incident_status
                note = (
                    f"Report linked to existing incident {incident.id}; no separate work order created."
                    if linked
                    else f"Incident {incident.id} routed to {dept_name}; work order is {work_order.id if work_order else 'not created'} (SLA {sla_hours}h)."
                )

            session.add(ComplaintTimeline(
                complaint_id=complaint.id,
                status=complaint.status,
                note=note,
                changed_by_id=human_decision.get("officer_id"),
            ))
            reporter = await session.get(User, complaint.citizen_id)
            reporter_user_id = reporter.id if reporter else None
            persisted_incident_id = incident.id
            link_event_id = link.id
            link_event_key = f"report-link:{link.id}"
            has_link_event = await session.scalar(select(IncidentTimeline.id).where(
                IncidentTimeline.event_key == link_event_key
            ))
            if has_link_event is None:
                session.add(IncidentTimeline(
                    incident_id=incident.id,
                    actor_id=complaint.citizen_id,
                    event_type=("report_linked" if linked else "duplicate_review_queued" if decision == "officer_review" else "work_order_created"),
                    event_key=link_event_key,
                    status=incident.status.value,
                    note=(
                        "A citizen report was linked to this incident."
                        if linked else "A possible duplicate is waiting for officer review." if decision == "officer_review" else "The incident was assigned to a municipal work order."
                    ),
                ))
            if status_changed and work_order is not None:
                status_event_key = f"incident-status:{incident.id}:{incident.status.value}:{work_order.id}"
                status_event_id = await session.scalar(select(IncidentTimeline.id).where(
                    IncidentTimeline.event_key == status_event_key
                ))
                if status_event_id is None:
                    status_event = IncidentTimeline(
                        incident_id=incident.id,
                        actor_id=human_decision.get("officer_id"),
                        event_type="status_changed",
                        event_key=status_event_key,
                        status=incident.status.value,
                        note=f"The incident is now {incident.status.value} with an active work order.",
                    )
                    session.add(status_event)
                    await session.flush()
                    status_event_id = status_event.id
            await session.commit()
            persisted_order_id = work_order.id if work_order else None
            external_id = work_order.external_id if work_order else None
            order_status = work_order.status if work_order else None
    except Exception as exc:
        logger.exception("Action persistence failed for complaint %s", complaint_id)
        return _result(state, {
            "work_order_id": None,
            "action_status": "failed",
            "error": f"{type(exc).__name__}: persistence failed",
            "notifications_queued": False,
            "dispatched_to": None,
        })

    if rejected:
        return _result(state, {
            "work_order_id": None,
            "action_status": "rejected",
            "notifications_queued": False,
            "dispatched_to": None,
            "timeline_note": note,
        })

    dispatch_error = None
    dispatch_result: dict[str, Any] = {}
    if work_order is not None and not external_id:
        try:
            external_id, order_status, dispatch_result = await _dispatch_work_order_once(
                work_order_id=persisted_order_id,
                complaint_id=str(complaint_id),
                department_code=routing.get("department_code", dept_name),
                priority=priority,
            )
        except Exception as exc:
            dispatch_error = f"{type(exc).__name__}: dispatch failed"
            logger.exception("Work order dispatch failed for order %s", persisted_order_id)

    notification_errors = []
    notification_results: dict[str, Any] = {}
    from app.services.incident_follow_up_service import IncidentFollowUpService

    try:
        async with async_session_factory() as session:
            incident = await session.get(Incident, persisted_incident_id) if persisted_incident_id else None
            if incident is not None and reporter_user_id:
                fanout = await IncidentFollowUpService.notify_reporters(
                    session,
                    incident,
                    event_type="report_linked" if linked else "work_order_created",
                    message=(
                        f"Your report was linked to Namma Civic incident {incident.id[:8]}."
                        if linked else
                        f"Your report is waiting for officer review for Namma Civic incident {incident.id[:8]}. No new work order was dispatched."
                        if decision == "officer_review" else
                        f"A work order for Namma Civic incident {incident.id[:8]} is {order_status or 'pending'} with {dept_name}. Target SLA: {sla_hours}h."
                    ),
                    event_key=f"report-link:{link_event_id}",
                    recipient_user_ids={reporter_user_id},
                )
                notification_results["reporter_update"] = fanout
            if incident is not None and status_changed and status_event_id:
                fanout = await IncidentFollowUpService.notify_reporters(
                    session,
                    incident,
                    event_type="status_changed",
                    message=f"Namma Civic incident {incident.id[:8]} is now {incident.status.value}.",
                    event_key=status_event_id,
                )
                notification_results["incident_status"] = fanout
            notification_errors = [
                f"{key}: {value['failed_count']} deliveries failed"
                for key, value in notification_results.items()
                if value.get("failed_count")
            ]
    except Exception as exc:
        notification_errors.append(f"{type(exc).__name__}: notification recording failed")
        logger.exception("Incident fan-out failed for complaint %s", complaint_id)

    status = "needs_review" if decision == "officer_review" else "linked" if linked else "dispatched" if external_id else "dispatch_failed" if dispatch_error else "queued"
    if work_order is None and not linked and decision != "officer_review":
        status = "work_order_not_created"
    return _result(state, {
        "work_order_id": external_id or persisted_order_id,
        "action_status": status,
        "match_decision": decision,
        "incident_id": persisted_incident_id,
        "notifications_queued": any(value.get("delivery_count", 0) for value in notification_results.values()),
        "notification_results": notification_results,
        "notification_errors": notification_errors,
        "dispatch_error": dispatch_error,
        "dispatched_to": dept_name if external_id else None,
        "timeline_note": note,
    })


async def _dispatch_work_order_once(
    work_order_id: str,
    complaint_id: str,
    department_code: str,
    priority: str,
) -> tuple[str | None, WorkOrderStatus | None, dict[str, Any]]:
    """Serialize dispatch claims by work order and reuse a prior external ID."""
    from app.mcp.client import mcp_client

    async with async_session_factory() as session:
        # Keep the same database-wide mutex through the external dispatch and
        # external-ID write. A concurrent linked report then sees that ID and
        # does not dispatch the shared work order a second time.
        await session.execute(
            update(Incident)
            .where(Incident.id == select(Incident.id).order_by(Incident.id).limit(1).scalar_subquery())
            .values(updated_at=Incident.updated_at)
        )
        stored_order = await session.scalar(
            select(WorkOrder).where(WorkOrder.id == work_order_id).with_for_update()
        )
        if stored_order is None:
            raise ValueError(f"Work order {work_order_id} was not found")
        if stored_order.external_id:
            return stored_order.external_id, stored_order.status, {}

        result = await mcp_client.call_tool("civic_work_order_dispatch", {
            "complaint_id": complaint_id,
            "department_code": department_code,
            "priority": priority,
            "idempotency_key": work_order_id,
        })
        external_id = result.get("work_order_id")
        if external_id:
            stored_order.external_id = external_id
            stored_order.status = WorkOrderStatus.assigned
        await session.commit()
        return external_id, stored_order.status, result


def _result(state: CivicActionState, action_result: Dict[str, Any]) -> Dict[str, Any]:
    """Add the action output and trace entry to graph state."""
    steps = list(state.get("steps_completed", []))
    if "action" not in steps:
        steps.append("action")
    return {
        "action_result": action_result,
        "current_step": "monitoring",
        "steps_completed": steps,
    }
