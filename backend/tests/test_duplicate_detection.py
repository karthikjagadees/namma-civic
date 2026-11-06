"""Tests for deterministic duplicate scoring and held-out synthetic evaluation."""
from datetime import datetime, timedelta, timezone

import pytest

from app.deduplication.engine import (
    CandidateIncident,
    MatchDecision,
    ReportEvidence,
    Thresholds,
    match_report,
    score_candidate,
)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def report(**changes):
    values = {
        "report_id": "report-new",
        "text": "Large pothole near the school entrance",
        "category": "pothole",
        "latitude": 12.9700,
        "longitude": 77.5900,
        "location_accuracy_m": 8.0,
        "address": "School Road",
        "landmark": "School entrance",
        "photo_hashes": ("ffffffffffffffff",),
        "channel": "mobile",
        "reported_at": NOW,
    }
    values.update(changes)
    return ReportEvidence(**values)


def candidate(**changes):
    values = {
        "incident_id": "incident-1",
        "title": "Pothole outside school",
        "report_texts": ("Deep road hole at the school gate",),
        "category": "pothole",
        "status": "open",
        "latitude": 12.97002,
        "longitude": 77.59002,
        "location_accuracy_m": 10.0,
        "address": "School Road",
        "landmark": "School gate",
        "photo_hashes": ("ffffffffffffffff",),
        "created_at": NOW - timedelta(days=2),
        "last_reported_at": NOW - timedelta(days=1),
    }
    values.update(changes)
    return CandidateIncident(**values)


def test_candidate_score_exposes_each_signal_and_uses_token_and_character_ngrams():
    scored = score_candidate(report(), candidate())

    assert set(scored.signals) == {
        "distance", "category", "token_similarity", "character_ngram_similarity",
        "image_phash", "time", "address_landmark",
    }
    assert scored.signals["distance"] > 0.8
    assert scored.signals["category"] == 1.0
    assert scored.signals["image_phash"] == 1.0
    assert scored.signals["character_ngram_similarity"] > 0.0
    assert 0.0 <= scored.fused_score <= 1.0


def test_uncertain_location_reduces_distance_signal_confidence():
    precise = score_candidate(report(location_accuracy_m=0.0), candidate(location_accuracy_m=0.0))
    uncertain = score_candidate(report(location_accuracy_m=60.0), candidate(location_accuracy_m=60.0))

    assert uncertain.signals["distance"] < precise.signals["distance"]


def test_low_geocoder_confidence_reduces_distance_signal():
    trusted = score_candidate(report(location_confidence=1.0), candidate())
    uncertain = score_candidate(report(location_confidence=0.25), candidate())

    assert uncertain.signals["distance"] < trusted.signals["distance"]


def test_different_categories_and_separate_nearby_issues_do_not_auto_link():
    result = match_report(
        report(category="garbage", text="Garbage pile at school gate"),
        [candidate(category="pothole", title="Pothole by gate", report_texts=("Pothole at school",))],
    )

    assert result.decision != MatchDecision.auto_link


def test_report_without_resolvable_coordinates_goes_to_officer_review_even_with_text_match():
    result = match_report(
        report(latitude=None, longitude=None, location_accuracy_m=None),
        [candidate()],
    )

    assert result.decision == MatchDecision.officer_review
    assert "location" in " ".join(result.reasons).lower()


def test_strong_match_to_resolved_incident_creates_recurrence_not_a_link():
    result = match_report(report(), [candidate(status="resolved")])

    assert result.decision == MatchDecision.new_incident
    assert result.incident_id is None
    assert result.recurrence_of_incident_id == "incident-1"


def test_ambiguous_resolved_candidate_is_reviewed_before_creating_recurrence():
    weak = candidate(
        status="resolved", photo_hashes=(), address="School Road", landmark="School entrance",
        latitude=12.9700, longitude=77.5900, report_texts=("Broken road surface",),
        title="Broken road surface", category="pothole",
    )
    result = match_report(report(photo_hashes=()), [weak], Thresholds(auto_link=0.67, review=0.58))

    assert result.decision == MatchDecision.officer_review
    assert result.recurrence_of_incident_id is None


def test_resolved_incident_outside_window_is_not_a_recurrence_candidate():
    stale = candidate(
        status="resolved", created_at=NOW - timedelta(days=500),
        last_reported_at=NOW - timedelta(days=500),
    )
    result = match_report(report(), [stale])

    assert result.decision == MatchDecision.new_incident
    assert result.recurrence_of_incident_id is None


def test_recent_report_on_an_older_incident_keeps_it_in_the_time_window():
    older = candidate(
        status="resolved", created_at=NOW - timedelta(days=500),
        last_reported_at=NOW - timedelta(days=1),
    )
    result = match_report(report(), [older])

    assert result.recurrence_of_incident_id == "incident-1"


def test_candidate_that_bridges_two_incidents_requires_officer_review():
    second = candidate(incident_id="incident-2", latitude=12.97001, title="Road damage")
    result = match_report(report(), [candidate(), second])

    assert result.decision == MatchDecision.officer_review
    assert "bridge" in " ".join(result.reasons).lower()


def test_unique_exact_photo_nearby_active_incident_wins_over_weaker_active_and_resolved_candidates():
    """A unique same-photo match should not pause just because nearby same-category cases exist."""
    report_at = datetime(2026, 11, 6, 2, 21, 37, tzinfo=timezone.utc)
    incoming = report(
        text="broken street light\nits to hard to see at night",
        category="street_light",
        latitude=12.89962825,
        longitude=77.49577149999999,
        address="BGS Road, Hemmigepura, Bengaluru",
        landmark="Hemmigepura",
        photo_hashes=("8a1b85a5f0d8f45e",),
        reported_at=report_at,
    )
    exact_active = candidate(
        incident_id="active-exact-photo",
        title="broken street light",
        report_texts=("its broken",),
        category="street_light",
        status="open",
        latitude=12.899732058388688,
        longitude=77.49579777939022,
        address="BGS Road, Hemmigepura, Bengaluru",
        landmark="Hemmigepura",
        photo_hashes=("8a1b85a5f0d8f45e",),
        created_at=report_at - timedelta(minutes=2),
        last_reported_at=report_at - timedelta(minutes=2),
    )
    nearby_active = candidate(
        incident_id="active-similar-photo",
        title="broken street light",
        report_texts=("its broken",),
        category="street_light",
        status="open",
        latitude=12.899774394760968,
        longitude=77.4958172378258,
        address="BGS Road, Hemmigepura, Bengaluru",
        landmark="Hemmigepura",
        photo_hashes=("fd38926f6190c867",),
        created_at=report_at - timedelta(minutes=3),
        last_reported_at=report_at - timedelta(minutes=3),
    )
    nearby_resolved = candidate(
        incident_id="resolved-similar-photo",
        title="broken street light",
        report_texts=("its broken",),
        category="street_light",
        status="resolved",
        latitude=12.899723718995181,
        longitude=77.49586325298482,
        address="BGS Road, Hemmigepura, Bengaluru",
        landmark="Hemmigepura",
        photo_hashes=("fd38926f6190c867",),
        created_at=report_at - timedelta(minutes=5),
        last_reported_at=report_at - timedelta(minutes=5),
    )

    result = match_report(incoming, [exact_active, nearby_active, nearby_resolved])

    assert result.decision == MatchDecision.auto_link
    assert result.incident_id == "active-exact-photo"


def test_unique_exact_photo_to_resolved_incident_creates_recurrence_over_weaker_active_candidates():
    """A unique strong match to a resolved case follows the recurrence policy."""
    incoming = report(
        category="street_light",
        latitude=12.899745549037641,
        longitude=77.49583813115312,
        address="BGS Road, Hemmigepura, Bengaluru",
        photo_hashes=("8a1b85a5f0d8f45e",),
    )
    exact_resolved = candidate(
        incident_id="resolved-exact-photo",
        category="street_light",
        status="resolved",
        latitude=12.899732058388688,
        longitude=77.49579777939022,
        address="BGS Road, Hemmigepura, Bengaluru",
        photo_hashes=("8a1b85a5f0d8f45e",),
    )
    nearby_active = candidate(
        incident_id="active-weaker-photo",
        category="street_light",
        status="open",
        latitude=12.899774394760968,
        longitude=77.4958172378258,
        address="BGS Road, Hemmigepura, Bengaluru",
        photo_hashes=("fd38926f6190c867",),
    )

    result = match_report(incoming, [exact_resolved, nearby_active])

    assert result.decision == MatchDecision.new_incident
    assert result.recurrence_of_incident_id == "resolved-exact-photo"


def test_same_exact_photo_match_to_both_active_and_resolved_incidents_stays_in_review():
    """Do not auto-link when identical photo evidence also points to a resolved case."""
    incoming = report(photo_hashes=("8a1b85a5f0d8f45e",))
    exact_resolved = candidate(incident_id="resolved-exact", status="resolved")

    result = match_report(incoming, [candidate(incident_id="active-exact"), exact_resolved])

    assert result.decision == MatchDecision.officer_review


def test_invalid_photo_hash_fails_safe_to_officer_review():
    result = match_report(report(), [candidate(photo_hashes=("not-a-phash",))])

    assert result.decision == MatchDecision.officer_review
    assert result.failures


def test_thresholds_are_selectable_using_calibration_partition_and_eval_dataset_is_synthetic():
    from app.deduplication.evaluation import build_synthetic_dataset, evaluate_thresholds

    dataset = build_synthetic_dataset()
    assert len(dataset) >= 150
    assert all(pair.dataset_kind == "synthetic" for pair in dataset)

    report_metrics = evaluate_thresholds(dataset)
    assert report_metrics.calibration_count > 0
    assert report_metrics.test_count > 0
    assert report_metrics.selected_thresholds.auto_link > report_metrics.selected_thresholds.review
    assert report_metrics.review_candidate_test_metrics.recall >= 0.0
    assert report_metrics.selected_thresholds == Thresholds()
    assert set(report_metrics.per_signal_test_metrics) >= {
        "distance", "category", "token_similarity", "character_ngram_similarity",
        "image_phash", "time", "address_landmark", "fused",
    }
    assert report_metrics.ablation_test_metrics


@pytest.mark.asyncio
async def test_candidate_query_uses_spatial_prefilter_not_a_global_incident_scan():
    from app.core.database import async_session_factory
    from app.deduplication.repository import retrieve_candidate_incidents
    from app.models.incident import Incident, IncidentStatus
    from app.models.complaint import Complaint, ComplaintCategory, ComplaintStatus, PriorityLevel
    from app.models.report_link import ReportLink
    from app.models.user import User
    from sqlalchemy import select

    async with async_session_factory() as session:
        nearby = CandidateIncident(
            incident_id="phase3-nearby", title="near", report_texts=("near",),
            category="pothole", status="open", latitude=1.0, longitude=1.0,
            created_at=NOW - timedelta(days=1), last_reported_at=NOW - timedelta(days=1),
        )
        far = CandidateIncident(
            incident_id="phase3-far", title="far", report_texts=("far",),
            category="pothole", status="open", latitude=20.0, longitude=20.0,
            created_at=NOW - timedelta(days=1), last_reported_at=NOW - timedelta(days=1),
        )
        session.add_all([
            Incident(id=nearby.incident_id, title=nearby.title, category="pothole", status=IncidentStatus.open,
                     latitude=nearby.latitude, longitude=nearby.longitude),
            Incident(id=far.incident_id, title=far.title, category="pothole", status=IncidentStatus.open,
                     latitude=far.latitude, longitude=far.longitude),
        ])
        await session.flush()
        citizen = await session.scalar(select(User).where(User.email == "citizen@demo.namma-civic.ai"))
        assert citizen is not None
        nearby_report = Complaint(
            citizen_id=citizen.id, title="nearby report", description="pothole",
            category=ComplaintCategory.pothole, status=ComplaintStatus.pending,
            priority=PriorityLevel.medium, latitude=1.0, longitude=1.0,
        )
        far_report = Complaint(
            citizen_id=citizen.id, title="far report", description="pothole",
            category=ComplaintCategory.pothole, status=ComplaintStatus.pending,
            priority=PriorityLevel.medium, latitude=20.0, longitude=20.0,
        )
        session.add_all([nearby_report, far_report])
        await session.flush()
        session.add_all([
            ReportLink(complaint_id=nearby_report.id, incident_id=nearby.incident_id, decision_source="auto"),
            ReportLink(complaint_id=far_report.id, incident_id=far.incident_id, decision_source="auto"),
        ])
        await session.flush()

        found = await retrieve_candidate_incidents(session, report(latitude=1.0, longitude=1.0))
        found_ids = {item.incident_id for item in found.candidates}
        await session.rollback()

    assert "phase3-nearby" in found_ids
    assert "phase3-far" not in found_ids


@pytest.mark.asyncio
async def test_database_candidate_failure_is_reported_as_review_not_no_match(monkeypatch):
    import importlib
    node_module = importlib.import_module("app.agents.nodes.deduplication_node")
    from app.agents.nodes.deduplication_node import deduplication_node

    class BrokenSession:
        async def __aenter__(self):
            raise RuntimeError("database unavailable")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(node_module, "async_session_factory", lambda: BrokenSession())
    result = await deduplication_node({
        "complaint_id": "phase3-report", "title": "Pothole", "description": "Large pothole",
        "category": "pothole", "latitude": 1.0, "longitude": 1.0,
        "steps_completed": [],
    })

    assert result["deduplication_result"]["decision"] == MatchDecision.officer_review.value
    assert result["deduplication_result"]["failures"]


@pytest.mark.asyncio
async def test_recurrence_incident_can_persist_link_to_prior_resolved_incident():
    from sqlalchemy import select
    from app.core.database import async_session_factory
    from app.models.incident import Incident, IncidentStatus
    from app.models.user import User
    from app.schemas.complaint import ComplaintCreateRequest
    from app.services.complaint_service import ComplaintService
    from app.services.incident_service import create_recurrence_incident_for_report

    async with async_session_factory() as session:
        citizen = await session.scalar(select(User).where(User.email == "citizen@demo.namma-civic.ai"))
        assert citizen is not None
        previous = Incident(title="Resolved pothole", category="pothole", status=IncidentStatus.resolved)
        session.add(previous)
        await session.flush()
        report = await ComplaintService(session).create_complaint(
            ComplaintCreateRequest(title="New pothole", description="It came back near the school"),
            citizen.id,
        )
        recurrence, recurrence_link = await create_recurrence_incident_for_report(
            session, report, previous.id, 0.88, {"distance": 0.9}
        )
        await session.flush()

        assert recurrence.recurrence_of_incident_id == previous.id
        assert recurrence_link.is_active is True
        assert recurrence_link.supersedes_link_id is not None
        await session.rollback()
