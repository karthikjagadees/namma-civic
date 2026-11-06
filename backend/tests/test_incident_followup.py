"""Phase 5 tests for incident-level citizen follow-up and transparency."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, select

from app.core.database import async_session_factory
from app.models.complaint import Complaint, ComplaintCategory, ComplaintStatus, PriorityLevel
from app.models.incident import Incident, IncidentStatus
from app.models.follow_up import IncidentTimeline
from app.models.report_link import ReportLink, ReportLinkDecisionSource
from app.models.user import User


async def _make_report(session, *, email: str, phone: str | None, incident: Incident, status=ComplaintStatus.assigned):
    """Create a synthetic citizen and linked report for follow-up tests."""
    user = User(
        email=email,
        hashed_password="unused-test-hash",
        full_name="Synthetic Citizen",
        phone=phone,
    )
    session.add(user)
    await session.flush()
    report = Complaint(
        citizen_id=user.id,
        title="Synthetic pothole report",
        description="A pothole needs repair on the sample road.",
        category=ComplaintCategory.pothole,
        status=status,
        priority=PriorityLevel.high,
        latitude=12.0,
        longitude=77.0,
    )
    session.add(report)
    await session.flush()
    link = ReportLink(
        complaint_id=report.id,
        incident_id=incident.id,
        decision_source=ReportLinkDecisionSource.auto,
    )
    session.add(link)
    await session.flush()
    return user, report


@pytest.mark.asyncio
async def test_public_tracker_shows_aggregate_status_without_reporter_data():
    from app.services.incident_follow_up_service import IncidentFollowUpService

    async with async_session_factory() as session:
        incident = Incident(
            title="Pothole on Sample Road", category=ComplaintCategory.pothole,
            status=IncidentStatus.in_progress, latitude=12.0, longitude=77.0,
            priority="high",
        )
        session.add(incident)
        await session.flush()
        first, _ = await _make_report(session, email=f"tracker-a-{uuid4().hex}@example.test", phone="+919911100001", incident=incident)
        await _make_report(session, email=f"tracker-b-{uuid4().hex}@example.test", phone="+919911100002", incident=incident)
        session.add(IncidentTimeline(
            incident_id=incident.id, actor_id=first.id, event_type="reporter_dispute_reopened",
            status="open", note=f"private synthetic detail: {first.email}",
        ))
        await session.flush()
        tracker = await IncidentFollowUpService.get_public_tracker(session, incident.id)

        assert tracker["incident_id"] == incident.id
        assert tracker["status"] == "in_progress"
        assert tracker["reporter_count"] == 2
        assert "timeline" in tracker and "expected_by" in tracker
        assert first.email not in repr(tracker)
        assert first.phone not in repr(tracker)
        assert "private synthetic detail" not in repr(tracker)
        assert "reporter_ids" not in tracker


@pytest.mark.asyncio
async def test_status_fanout_records_each_reporter_channel(monkeypatch):
    from app.mcp.client import mcp_client
    from app.models.follow_up import IncidentNotificationPreference, NotificationDelivery
    from app.services.incident_follow_up_service import IncidentFollowUpService

    sends = []

    async def send(name, payload):
        sends.append((name, payload))
        return {"status": "DELIVERED", "delivery_id": f"synthetic-{len(sends)}"}

    monkeypatch.setattr(mcp_client, "call_tool", send)
    async with async_session_factory() as session:
        incident = Incident(
            title="Pothole on Sample Road", category=ComplaintCategory.pothole,
            status=IncidentStatus.resolved, priority="high",
        )
        session.add(incident)
        await session.flush()
        sms_user, _ = await _make_report(session, email=f"follow-sms-{uuid4().hex}@example.test", phone="+919911100003", incident=incident)
        mail_user, _ = await _make_report(session, email=f"follow-mail-{uuid4().hex}@example.test", phone=None, incident=incident)
        session.add_all([
            IncidentNotificationPreference(user_id=sms_user.id, sms_enabled=True, email_enabled=False),
            IncidentNotificationPreference(user_id=mail_user.id, sms_enabled=False, email_enabled=True),
        ])
        await session.flush()

        result = await IncidentFollowUpService.notify_reporters(
            session, incident, event_type="resolved", message="Synthetic incident resolved.",
        )
        records = list((await session.scalars(select(NotificationDelivery).where(
            NotificationDelivery.incident_id == incident.id
        ))).all())

        assert result["recipient_count"] == 2
        assert {record.channel for record in records} == {"sms", "email"}
        assert all(record.status == "delivered" for record in records)
        assert len(sends) == 2


@pytest.mark.asyncio
async def test_failed_notification_is_saved_per_channel(monkeypatch):
    from app.mcp.client import mcp_client
    from app.models.follow_up import NotificationDelivery
    from app.services.incident_follow_up_service import IncidentFollowUpService

    async def fail_send(_name, _payload):
        raise RuntimeError("synthetic notification gateway failure")

    monkeypatch.setattr(mcp_client, "call_tool", fail_send)
    async with async_session_factory() as session:
        incident = Incident(title="Synthetic failed delivery", category=ComplaintCategory.pothole)
        session.add(incident)
        await session.flush()
        await _make_report(session, email=f"delivery-fail-{uuid4().hex}@example.test", phone="+919911100005", incident=incident)
        result = await IncidentFollowUpService.notify_reporters(
            session, incident, event_type="status_changed", message="Synthetic status update.", event_key="synthetic-failure-event",
        )
        deliveries = list((await session.scalars(select(NotificationDelivery).where(
            NotificationDelivery.incident_id == incident.id
        ))).all())

        assert result["failed_count"] == 2
        assert all(delivery.status == "failed" for delivery in deliveries)
        assert all("gateway failure" not in delivery.error for delivery in deliveries)
        assert all("delivery failed" in delivery.error for delivery in deliveries)


@pytest.mark.asyncio
async def test_incident_sla_worker_escalates_the_shared_incident_once(monkeypatch):
    from app.mcp.client import mcp_client
    from app.models.follow_up import IncidentTimeline
    from app.services.sla_service import SLAService

    calls = []

    async def send(name, payload):
        calls.append((name, payload))
        return {"status": "DELIVERED"}

    monkeypatch.setattr(mcp_client, "call_tool", send)
    async with async_session_factory() as session:
        incident = Incident(
            title="Synthetic overdue incident", category=ComplaintCategory.pothole,
            status=IncidentStatus.in_progress, priority="low",
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
        )
        session.add(incident)
        await session.flush()
        first = await SLAService.scan_incidents_and_auto_escalate(session)
        second = await SLAService.scan_incidents_and_auto_escalate(session)
        event = await session.scalar(select(IncidentTimeline).where(
            IncidentTimeline.incident_id == incident.id,
            IncidentTimeline.event_type == "sla_escalation",
        ))

        assert first["escalated_count"] == 1
        assert second["escalated_count"] == 0
        assert event is not None
        assert len(calls) == 1


@pytest.mark.asyncio
async def test_reporter_can_reopen_resolved_incident_and_it_is_audited():
    from app.models.follow_up import IncidentTimeline
    from app.services.incident_follow_up_service import IncidentFollowUpService

    async with async_session_factory() as session:
        incident = Incident(
            title="Resolved sample pothole", category=ComplaintCategory.pothole,
            status=IncidentStatus.resolved, resolved_at=datetime.now(timezone.utc), priority="high",
        )
        session.add(incident)
        await session.flush()
        reporter, _ = await _make_report(session, email=f"dispute-{uuid4().hex}@example.test", phone=None, incident=incident, status=ComplaintStatus.resolved)

        result = await IncidentFollowUpService.dispute_and_reopen(
            session, incident.id, reporter.id, "Synthetic report says the defect remains.",
        )
        event = await session.scalar(select(IncidentTimeline).where(
            IncidentTimeline.incident_id == incident.id,
            IncidentTimeline.event_type == "reporter_dispute_reopened",
        ))

        assert result["status"] == "open"
        assert incident.resolved_at is None
        assert event is not None and event.actor_id == reporter.id


@pytest.mark.asyncio
async def test_tracker_and_preferences_api_are_available_to_the_authenticated_reporter():
    from app.core.security import create_access_token
    from app.main import app
    from app.models.follow_up import IncidentNotificationPreference

    async with async_session_factory() as session:
        incident = Incident(
            title="API sample incident", category=ComplaintCategory.pothole,
            status=IncidentStatus.open, priority="medium",
        )
        session.add(incident)
        await session.flush()
        reporter, report = await _make_report(
            session, email=f"api-tracker-{uuid4().hex}@example.test", phone="+919911100004", incident=incident,
        )
        await session.commit()
        report_id = report.id
        token = create_access_token(subject=reporter.id, role="citizen")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token}"}
        tracker = await client.get(f"/api/incidents/by-report/{report_id}/tracker", headers=headers)
        assert tracker.status_code == 200
        assert tracker.json()["reporter_count"] == 1
        assert "reporter_ids" not in tracker.json()

        saved = await client.put(
            "/api/notifications/preferences",
            json={"sms_enabled": False, "email_enabled": True},
            headers=headers,
        )
        assert saved.status_code == 200
        assert saved.json() == {"sms_enabled": False, "email_enabled": True}

    async with async_session_factory() as session:
        preference = await session.get(IncidentNotificationPreference, reporter.id)
        assert preference is not None and preference.sms_enabled is False


def test_phase_five_migration_is_registered():
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "migrations"))
    revisions = {revision.revision for revision in ScriptDirectory.from_config(config).walk_revisions()}

    assert "0004_incident_follow_up" in revisions


def test_incident_sla_is_calculated_from_incident_priority_and_age():
    from app.services.sla_service import SLAService

    incident = Incident(
        id="synthetic-old-incident", title="Synthetic overdue road repair",
        category=ComplaintCategory.pothole, status=IncidentStatus.in_progress,
        priority="low", created_at=datetime.now(timezone.utc) - timedelta(days=5),
    )

    result = SLAService.calculate_incident_sla(incident)

    assert result["incident_id"] == incident.id
    assert result["total_sla_hours"] == 72
    assert result["sla_status"] == "BREACHED"
