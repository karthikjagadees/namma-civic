"""Phase 6 tests for audited duplicate review and officer feedback."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.database import async_session_factory
from app.models.complaint import Complaint, ComplaintCategory, ComplaintMedia, ComplaintStatus, MediaType, PriorityLevel
from app.models.incident import Incident, IncidentStatus
from app.models.report_link import ReportLink, ReportLinkDecisionSource
from app.models.user import User, UserRole
from app.models.work_order import WorkOrder, WorkOrderStatus


async def _case(*, with_candidate_order: bool = True, candidate_status=IncidentStatus.in_progress):
    """Create an isolated officer, reporter, two incidents, and a pending review."""
    from app.models.duplicate_review import DuplicateReviewCase

    suffix = uuid4().hex
    async with async_session_factory() as session:
        officer = User(
            email=f"officer-{suffix}@review.test", hashed_password="unused",
            full_name="Review Officer", role=UserRole.officer,
        )
        citizen = User(
            email=f"citizen-{suffix}@review.test", hashed_password="unused",
            full_name="Review Citizen", role=UserRole.citizen,
        )
        session.add_all([officer, citizen])
        await session.flush()
        source = Incident(title="Pothole report", category=ComplaintCategory.pothole, status=IncidentStatus.open,
                          latitude=12.97, longitude=77.59)
        candidate = Incident(title="Road hole", category=ComplaintCategory.pothole, status=candidate_status,
                             latitude=12.9701, longitude=77.59)
        session.add_all([source, candidate])
        await session.flush()
        complaint = Complaint(
            citizen_id=citizen.id, title="Large road hole", description="A deep pothole near the library.",
            category=ComplaintCategory.pothole, status=ComplaintStatus.assigned,
            priority=PriorityLevel.medium, latitude=12.97, longitude=77.59,
            address="Library Road", source="web",
        )
        other = Complaint(
            citizen_id=citizen.id, title="Road crater", description="The pavement is damaged.",
            category=ComplaintCategory.pothole, status=ComplaintStatus.assigned,
            priority=PriorityLevel.medium, latitude=12.9701, longitude=77.59,
            address="Library Road", source="mobile",
        )
        session.add_all([complaint, other])
        await session.flush()
        session.add_all([
            ComplaintMedia(complaint_id=complaint.id, media_type=MediaType.image,
                           file_url="/uploads/review-new-report.jpg", file_name="new-report.jpg", mime_type="image/jpeg"),
            ComplaintMedia(complaint_id=other.id, media_type=MediaType.image,
                           file_url="/uploads/review-candidate.jpg", file_name="candidate.jpg", mime_type="image/jpeg"),
        ])
        await session.flush()
        source_link = ReportLink(complaint_id=complaint.id, incident_id=source.id,
                                 decision_source=ReportLinkDecisionSource.auto)
        candidate_link = ReportLink(complaint_id=other.id, incident_id=candidate.id,
                                    decision_source=ReportLinkDecisionSource.auto)
        session.add_all([source_link, candidate_link])
        source_order = WorkOrder(incident_id=source.id, status=WorkOrderStatus.queued, priority="medium")
        candidate_order = None
        if with_candidate_order:
            candidate_order = WorkOrder(incident_id=candidate.id, status=WorkOrderStatus.assigned, priority="high")
            session.add(candidate_order)
        session.add(source_order)
        review = DuplicateReviewCase(
            complaint_id=complaint.id,
            status="pending",
            reason="Synthetic test review",
            failures=[],
            candidates=[{
                "incident_id": candidate.id,
                "score": 0.61,
                "distance_m": 11.2,
                "signals": {"distance": 0.8, "category": 1.0, "image_phash": None},
            }],
        )
        session.add(review)
        await session.commit()
        return {
            "review_id": review.id, "complaint_id": complaint.id,
            "source_id": source.id, "candidate_id": candidate.id,
            "officer_id": officer.id, "title": complaint.title,
            "description": complaint.description, "source_order_id": source_order.id,
            "candidate_order_id": candidate_order.id if candidate_order else None,
        }


@pytest.mark.asyncio
async def test_review_queue_includes_side_by_side_report_candidate_map_photos_and_signals():
    from app.services.duplicate_review_service import DuplicateReviewService

    ids = await _case()
    async with async_session_factory() as session:
        queue = await DuplicateReviewService.list_queue(session)
    item = next(row for row in queue if row["review_id"] == ids["review_id"])
    assert item["report"]["description"] == ids["description"]
    assert item["report"]["location"]["latitude"] == pytest.approx(12.97)
    assert item["candidates"][0]["incident_id"] == ids["candidate_id"]
    assert item["candidates"][0]["signals"]["category"] == 1.0
    assert item["report"]["photos"][0]["url"] == "/uploads/review-new-report.jpg"
    assert item["candidates"][0]["photos"][0]["url"] == "/uploads/review-candidate.jpg"


@pytest.mark.asyncio
async def test_action_node_persists_review_case_and_holds_work_order_for_grey_zone(monkeypatch):
    import importlib

    action_module = importlib.import_module("app.agents.nodes.action_node")
    from app.deduplication.engine import CandidateScore, MatchDecision, MatchResult
    from app.models.duplicate_review import DuplicateReviewCase
    from app.services.incident_service import create_initial_incident_for_report

    suffix = uuid4().hex
    async with async_session_factory() as session:
        citizen = User(email=f"action-{suffix}@review.test", hashed_password="unused", full_name="Action Reporter")
        session.add(citizen)
        await session.flush()
        complaint = Complaint(
            citizen_id=citizen.id, title="Possible nearby pothole", description="Needs a duplicate check.",
            category=ComplaintCategory.pothole, status=ComplaintStatus.pending,
            priority=PriorityLevel.medium, latitude=12.97, longitude=77.59, source="web",
        )
        session.add(complaint)
        await session.flush()
        incident, _ = await create_initial_incident_for_report(session, complaint)
        complaint_id = complaint.id
        incident_id = incident.id
        await session.commit()

    async def review_result(_session, _evidence):
        return MatchResult(
            MatchDecision.officer_review,
            candidate_scores=(CandidateScore(
                incident_id=incident_id, fused_score=0.61,
                signals={"distance": 0.7, "category": 1.0}, distance_m=20.0,
            ),),
            reasons=("Grey-zone match needs an officer.",),
        )

    monkeypatch.setattr(action_module, "resolve_report_against_incidents", review_result)
    result = await action_module.action_node({
        "complaint_id": complaint_id,
        "routing_result": {"priority": "medium", "sla_hours": 48},
        "deduplication_result": {"decision": "officer_review"},
    })
    async with async_session_factory() as session:
        review = await session.scalar(select(DuplicateReviewCase).where(DuplicateReviewCase.complaint_id == complaint_id))
        order_count = await session.scalar(select(func.count(WorkOrder.id)).where(WorkOrder.incident_id == incident_id))
    assert review.status == "pending"
    assert review.candidates[0]["incident_id"] == incident_id
    assert order_count == 0
    assert result["action_result"]["action_status"] == "needs_review"


@pytest.mark.asyncio
async def test_confirm_link_preserves_history_and_saves_positive_label_and_audit():
    from app.models.duplicate_review import DuplicateReviewDecision
    from app.models.follow_up import IncidentTimeline
    from app.services.duplicate_review_service import DuplicateReviewService

    ids = await _case()
    async with async_session_factory() as session:
        result = await DuplicateReviewService.decide(
            session, ids["review_id"], ids["officer_id"], action="confirm_link",
            candidate_incident_id=ids["candidate_id"], note="Same pothole after photo review.",
        )
        links = list((await session.scalars(select(ReportLink).where(
            ReportLink.complaint_id == ids["complaint_id"],
        ).order_by(ReportLink.created_at))).all())
        label = await session.scalar(select(DuplicateReviewDecision).where(
            DuplicateReviewDecision.review_case_id == ids["review_id"],
        ))
        audit = await session.scalar(select(IncidentTimeline).where(
            IncidentTimeline.event_type == "duplicate_review_confirm_link",
            IncidentTimeline.actor_id == ids["officer_id"],
        ))
    assert result["status"] == "resolved"
    assert len(links) == 2 and not links[0].is_active and links[1].is_active
    assert links[1].incident_id == ids["candidate_id"]
    assert label.is_duplicate is True and label.officer_id == ids["officer_id"]
    assert audit is not None


@pytest.mark.asyncio
async def test_reject_match_keeps_report_incident_and_saves_negative_label():
    from app.models.duplicate_review import DuplicateReviewDecision
    from app.services.duplicate_review_service import DuplicateReviewService

    ids = await _case()
    async with async_session_factory() as session:
        await DuplicateReviewService.decide(
            session, ids["review_id"], ids["officer_id"], action="reject_match",
            candidate_incident_id=ids["candidate_id"], note="Different block of road.",
        )
        link = await session.scalar(select(ReportLink).where(
            ReportLink.complaint_id == ids["complaint_id"], ReportLink.is_active.is_(True),
        ))
        label = await session.scalar(select(DuplicateReviewDecision).where(
            DuplicateReviewDecision.review_case_id == ids["review_id"],
        ))
        active_order = await session.scalar(select(WorkOrder).where(
            WorkOrder.incident_id == ids["source_id"],
            WorkOrder.status.not_in((WorkOrderStatus.completed, WorkOrderStatus.cancelled)),
        ))
        complaint = await session.get(Complaint, ids["complaint_id"])
    assert link.incident_id == ids["source_id"]
    assert label.is_duplicate is False
    assert active_order is not None
    assert complaint.status == ComplaintStatus.assigned


@pytest.mark.asyncio
async def test_confirming_match_to_resolved_incident_creates_recurrence_instead_of_reopening_history():
    from app.services.duplicate_review_service import DuplicateReviewService

    ids = await _case(candidate_status=IncidentStatus.resolved, with_candidate_order=False)
    async with async_session_factory() as session:
        result = await DuplicateReviewService.decide(
            session, ids["review_id"], ids["officer_id"], action="confirm_link",
            candidate_incident_id=ids["candidate_id"], note="Same location, defect recurred after repair.",
        )
        recurrence = await session.get(Incident, result["incident_id"])
        active_order = await session.scalar(select(WorkOrder).where(
            WorkOrder.incident_id == recurrence.id,
            WorkOrder.status.not_in((WorkOrderStatus.completed, WorkOrderStatus.cancelled)),
        ))
    assert recurrence.recurrence_of_incident_id == ids["candidate_id"]
    assert recurrence.status == IncidentStatus.in_progress
    assert active_order is not None


@pytest.mark.asyncio
async def test_merge_moves_all_source_reports_and_leaves_one_active_work_order():
    from app.models.duplicate_review import DuplicateReviewDecision
    from app.services.duplicate_review_service import DuplicateReviewService

    ids = await _case()
    async with async_session_factory() as session:
        linked_report = Complaint(
            citizen_id=(await session.get(Complaint, ids["complaint_id"])).citizen_id,
            title="Second report in the source incident", description="Another preserved source report.",
            category=ComplaintCategory.pothole, status=ComplaintStatus.assigned,
            priority=PriorityLevel.medium, source="whatsapp",
        )
        session.add(linked_report)
        await session.flush()
        session.add(ReportLink(
            complaint_id=linked_report.id, incident_id=ids["source_id"],
            decision_source=ReportLinkDecisionSource.auto,
        ))
        linked_report_id = linked_report.id
        await session.commit()
        await DuplicateReviewService.decide(
            session, ids["review_id"], ids["officer_id"], action="merge_incidents",
            candidate_incident_id=ids["candidate_id"], note="Officer merged the clusters.",
        )
        active_links = list((await session.scalars(select(ReportLink).join(Complaint).where(
            Complaint.id.in_([ids["complaint_id"], linked_report_id]), ReportLink.is_active.is_(True),
        ))).all())
        active_orders = list((await session.scalars(select(WorkOrder).where(
            WorkOrder.incident_id == ids["candidate_id"],
            WorkOrder.status.not_in((WorkOrderStatus.completed, WorkOrderStatus.cancelled)),
        ))).all())
        canceled_source = await session.get(WorkOrder, ids["source_order_id"])
        label = await session.scalar(select(DuplicateReviewDecision).where(
            DuplicateReviewDecision.review_case_id == ids["review_id"],
        ))
    assert len(active_links) == 2 and all(link.incident_id == ids["candidate_id"] for link in active_links)
    assert len(active_orders) == 1
    assert canceled_source.status == WorkOrderStatus.cancelled
    assert label.is_duplicate is True and label.action == "merge_incidents"


@pytest.mark.asyncio
async def test_split_creates_separate_incident_and_keeps_original_report_evidence():
    from app.models.duplicate_review import DuplicateReviewDecision
    from app.services.duplicate_review_service import DuplicateReviewService

    ids = await _case()
    async with async_session_factory() as session:
        result = await DuplicateReviewService.decide(
            session, ids["review_id"], ids["officer_id"], action="split_report",
            candidate_incident_id=ids["candidate_id"], note="Reports concern different potholes.",
        )
        complaint = await session.get(Complaint, ids["complaint_id"])
        link = await session.scalar(select(ReportLink).where(
            ReportLink.complaint_id == complaint.id, ReportLink.is_active.is_(True),
        ))
        label = await session.scalar(select(DuplicateReviewDecision).where(
            DuplicateReviewDecision.review_case_id == ids["review_id"],
        ))
    assert link.incident_id == result["new_incident_id"]
    assert link.incident_id != ids["candidate_id"]
    assert complaint.title == ids["title"] and complaint.description == ids["description"]
    assert label.is_duplicate is False


@pytest.mark.asyncio
async def test_duplicate_operations_analytics_uses_saved_links_work_orders_and_officer_labels():
    from app.models.duplicate_review import DuplicateReviewDecision
    from app.services.duplicate_review_service import DuplicateReviewService

    ids = await _case()
    async with async_session_factory() as session:
        second_officer = User(
            email=f"second-officer-{uuid4().hex}@review.test", hashed_password="unused",
            full_name="Second Review Officer", role=UserRole.officer,
        )
        linked_citizen = User(
            email=f"linked-citizen-{uuid4().hex}@review.test", hashed_password="unused",
            full_name="Another Citizen", role=UserRole.citizen,
        )
        session.add_all([second_officer, linked_citizen])
        await session.flush()
        duplicate_report = Complaint(
            citizen_id=linked_citizen.id, title="Another report of same road defect",
            description="A pothole is at this exact location.", category=ComplaintCategory.pothole,
            status=ComplaintStatus.assigned, priority=PriorityLevel.medium,
            latitude=12.9701, longitude=77.59, source="mobile",
        )
        session.add(duplicate_report)
        await session.flush()
        session.add(ReportLink(
            complaint_id=duplicate_report.id, incident_id=ids["candidate_id"],
            decision_source=ReportLinkDecisionSource.officer,
        ))
        session.add_all([
            DuplicateReviewDecision(review_case_id=ids["review_id"], complaint_id=ids["complaint_id"],
                                    candidate_incident_id=ids["candidate_id"], officer_id=ids["officer_id"],
                                    action="confirm_link", is_duplicate=True, score=0.61, evidence={}),
            DuplicateReviewDecision(review_case_id=ids["review_id"], complaint_id=ids["complaint_id"],
                                    candidate_incident_id=ids["candidate_id"], officer_id=second_officer.id,
                                    action="confirm_link", is_duplicate=True, score=0.61, evidence={}),
        ])
        await session.commit()
        metrics = await DuplicateReviewService.analytics(session)
    assert metrics["duplicates_linked"] >= 1
    assert metrics["work_orders_avoided"] >= 1
    assert metrics["review_queue_volume"] >= 1
    assert metrics["officer_agreement_rate"] == pytest.approx(1.0)


def test_officer_threshold_recommendation_does_not_apply_new_thresholds_implicitly():
    from app.deduplication.officer_calibration import recommend_thresholds
    from app.deduplication.engine import Thresholds

    current = Thresholds(auto_link=0.66, review=0.58)
    labels = [(0.91, True), (0.86, True), (0.61, True), (0.59, False), (0.41, False)]
    recommendation = recommend_thresholds(labels, current)
    assert recommendation.current == current
    assert recommendation.proposed.auto_link >= recommendation.proposed.review
    assert recommendation.applied is False


@pytest.mark.asyncio
async def test_duplicate_review_routes_are_officer_protected():
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from tests.test_agents import get_token

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        citizen_token = await get_token(client, {"email": "citizen@demo.namma-civic.ai", "password": "password123"}, is_register=False)
        response = await client.get("/api/officer/duplicate-reviews", headers={"Authorization": f"Bearer {citizen_token}"})
        metrics_response = await client.get("/api/analytics/duplicate-operations", headers={"Authorization": f"Bearer {citizen_token}"})
        officer_token = await get_token(client, {"email": "officer@demo.namma-civic.ai", "password": "password123"}, is_register=False)
        queue_response = await client.get("/api/officer/duplicate-reviews", headers={"Authorization": f"Bearer {officer_token}"})
    assert response.status_code == 403
    assert metrics_response.status_code == 403
    assert queue_response.status_code == 200


def test_phase_6_and_phase_7_alembic_revisions_are_present():
    from pathlib import Path
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    revisions = ScriptDirectory.from_config(config)
    assert "0005_officer_duplicate_review" in {item.revision for item in revisions.walk_revisions()}
    assert "0006_phase7_hardening" in {item.revision for item in revisions.walk_revisions()}
    assert revisions.get_current_head() == "0007_complaint_tracking_id"
