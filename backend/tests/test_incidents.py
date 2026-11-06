"""Tests for the incident data model and its migration/backfill."""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.complaint import Complaint, ComplaintCategory, ComplaintStatus, PriorityLevel
from app.models.user import User
from app.schemas.complaint import ComplaintCreateRequest
from app.services.complaint_service import ComplaintService


def _alembic_config() -> Config:
    """Create Alembic configuration rooted at the backend directory."""
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "migrations"))
    return config


async def _create_report(session, suffix: str) -> Complaint:
    """Create a complaint using the deterministic demo citizen."""
    citizen = await session.scalar(
        select(User).where(User.email == "citizen@demo.namma-civic.ai")
    )
    assert citizen is not None
    report = Complaint(
        citizen_id=citizen.id,
        title=f"Pothole report {suffix}",
        description="Deep pothole near the bus stop.",
        category=ComplaintCategory.pothole,
        status=ComplaintStatus.pending,
        priority=PriorityLevel.medium,
        latitude=12.9716,
        longitude=77.5946,
    )
    session.add(report)
    await session.flush()
    return report


@pytest.mark.asyncio
async def test_one_active_report_link_and_audited_reassignment():
    """A report has one current link while a prior officer decision is retained."""
    from app.models.incident import Incident, IncidentStatus
    from app.models.report_link import ReportLink, ReportLinkDecisionSource
    from app.services.incident_service import reassign_report_link

    async with async_session_factory() as session:
        report = await _create_report(session, "link")
        first_incident = Incident(
            title=report.title,
            category=report.category,
            status=IncidentStatus.open,
            latitude=report.latitude,
            longitude=report.longitude,
        )
        second_incident = Incident(
            title="Nearby but separate pothole",
            category=ComplaintCategory.pothole,
            status=IncidentStatus.open,
            latitude=12.9720,
            longitude=77.5950,
        )
        session.add_all([first_incident, second_incident])
        await session.flush()

        officer = await session.scalar(
            select(User).where(User.email == "officer@demo.namma-civic.ai")
        )
        assert officer is not None
        historical_link = ReportLink(
            complaint_id=report.id,
            incident_id=first_incident.id,
            decision_source=ReportLinkDecisionSource.backfill,
        )
        session.add(historical_link)
        await session.flush()
        active_link = await reassign_report_link(
            session=session,
            link_id=historical_link.id,
            new_incident_id=second_incident.id,
            officer_id=officer.id,
            decision_note="Officer confirmed these are separate defects.",
            match_score=0.91,
            signal_evidence={"distance_m": 42.0},
        )
        await session.commit()

        assert historical_link.is_active is False
        assert historical_link.ended_at is not None
        assert active_link.is_active is True
        assert active_link.supersedes_link_id == historical_link.id
        assert active_link.decision_source == ReportLinkDecisionSource.officer
        assert active_link.decision_note == "Officer confirmed these are separate defects."

        duplicate_active = ReportLink(
            complaint_id=report.id,
            incident_id=first_incident.id,
            decision_source=ReportLinkDecisionSource.auto,
            is_active=True,
        )
        session.add(duplicate_active)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


@pytest.mark.asyncio
async def test_only_one_active_work_order_per_incident():
    """A completed work order may be followed by one active order, never two."""
    from app.models.incident import Incident, IncidentStatus
    from app.models.work_order import WorkOrder, WorkOrderStatus

    async with async_session_factory() as session:
        report = await _create_report(session, "work-order")
        incident = Incident(
            title=report.title,
            category=report.category,
            status=IncidentStatus.open,
            latitude=report.latitude,
            longitude=report.longitude,
        )
        session.add(incident)
        await session.flush()
        incident_id = incident.id

        first_order = WorkOrder(
            incident_id=incident.id,
            status=WorkOrderStatus.assigned,
        )
        session.add(first_order)
        await session.commit()
        first_order_id = first_order.id

        second_order = WorkOrder(
            incident_id=incident_id,
            status=WorkOrderStatus.in_progress,
        )
        session.add(second_order)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

        first_order = await session.get(WorkOrder, first_order_id)
        assert first_order is not None
        first_order.status = WorkOrderStatus.completed
        await session.commit()

        replacement_order = WorkOrder(
            incident_id=incident_id,
            status=WorkOrderStatus.assigned,
        )
        session.add(replacement_order)
        await session.commit()


@pytest.mark.asyncio
async def test_new_complaint_gets_an_initial_incident_link():
    """The supported complaint intake path creates the report and incident atomically."""
    from app.models.incident import Incident
    from app.models.report_link import ReportLink, ReportLinkDecisionSource

    async with async_session_factory() as session:
        citizen = await session.scalar(
            select(User).where(User.email == "citizen@demo.namma-civic.ai")
        )
        assert citizen is not None
        request = ComplaintCreateRequest(
            title="New pothole near the station",
            description="A deep hole is damaging vehicles by the bus stop.",
            category=ComplaintCategory.pothole,
            latitude=12.9716,
            longitude=77.5946,
        )

        report = await ComplaintService(session).create_complaint(request, citizen.id)
        link = await session.scalar(
            select(ReportLink).where(
                ReportLink.complaint_id == report.id,
                ReportLink.is_active.is_(True),
            )
        )

        assert link is not None
        assert link.decision_source == ReportLinkDecisionSource.auto
        incident = await session.get(Incident, link.incident_id)
        assert incident is not None
        assert incident.title == report.title
        assert incident.category == report.category
        assert report.citizen_id == citizen.id


@pytest.mark.asyncio
async def test_demo_seed_reports_have_active_incident_links():
    """Demo seed data follows the same report-to-incident rule as API intake."""
    from app.models.report_link import ReportLink

    async with async_session_factory() as session:
        report = await session.scalar(
            select(Complaint).where(
                Complaint.title == "Severe Pothole Cluster & Caving Asphalt on 100ft Ring Road"
            )
        )
        assert report is not None
        link = await session.scalar(
            select(ReportLink).where(
                ReportLink.complaint_id == report.id,
                ReportLink.is_active.is_(True),
            )
        )
        assert link is not None


def test_alembic_contains_baseline_and_incident_revision():
    """Fresh databases need a baseline followed by an additive incident revision."""
    revisions = list(ScriptDirectory.from_config(_alembic_config()).walk_revisions())
    assert len(revisions) >= 2
    assert any(revision.revision == "0001_baseline" for revision in revisions)
    assert any(revision.revision == "0002_incidents" for revision in revisions)


@pytest.mark.asyncio
async def test_migrated_schema_matches_current_models():
    """Alembic head should not leave model tables or indexes unrepresented."""
    await asyncio.to_thread(command.check, _alembic_config())


@pytest.mark.asyncio
async def test_incident_migration_backfills_legacy_reports(tmp_path, monkeypatch):
    """Upgrade an old-schema database and preserve its reports while backfilling."""
    database_path = tmp_path / "legacy.sqlite3"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setattr(settings, "database_url", database_url)
    config = _alembic_config()

    await asyncio.to_thread(command.upgrade, config, "0001_baseline")
    created_at = "2025-01-02 03:04:05"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO users "
            "(id, email, hashed_password, full_name, role, is_active, is_verified, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("citizen-1", "legacy@example.test", "hashed", "Legacy Citizen", "citizen", 1, 1, created_at, created_at),
        )
        connection.execute(
            "INSERT INTO complaints "
            "(id, citizen_id, title, description, category, status, priority, severity, latitude, longitude, source, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "complaint-1", "citizen-1", "Legacy pothole", "Deep hole at the junction",
                "pothole", "in_progress", "high", 7, 12.9716, 77.5946, "web", created_at, created_at,
            ),
        )
        connection.execute(
            "INSERT INTO complaint_media "
            "(id, complaint_id, media_type, file_url, file_name, file_size, mime_type, is_resolution_evidence, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("media-1", "complaint-1", "image", "/uploads/original.jpg", "original.jpg", 1234,
             "image/jpeg", 0, created_at),
        )

    await asyncio.to_thread(command.upgrade, config, "head")
    with sqlite3.connect(database_path) as connection:
        incident = connection.execute(
            "SELECT title, category, status, latitude, longitude FROM incidents"
        ).fetchone()
        link = connection.execute(
            "SELECT complaint_id, decision_source, is_active, match_score FROM report_links"
        ).fetchone()
        original = connection.execute(
            "SELECT citizen_id, title, description, source, latitude, longitude FROM complaints WHERE id = ?",
            ("complaint-1",),
        ).fetchone()
        original_media = connection.execute(
            "SELECT file_url, file_name, mime_type FROM complaint_media WHERE id = ?",
            ("media-1",),
        ).fetchone()

    assert incident == ("Legacy pothole", "pothole", "in_progress", 12.9716, 77.5946)
    assert link == ("complaint-1", "backfill", 1, None)
    assert original == (
        "citizen-1", "Legacy pothole", "Deep hole at the junction", "web", 12.9716, 77.5946
    )
    assert original_media == ("/uploads/original.jpg", "original.jpg", "image/jpeg")


@pytest.mark.asyncio
async def test_startup_adopts_complete_unversioned_legacy_schema(tmp_path, monkeypatch):
    """Application startup stamps a complete create_all schema before upgrade."""
    from app.core import database

    database_path = tmp_path / "unversioned.sqlite3"
    database_url = f"sqlite:///{database_path.as_posix()}"
    async_database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    monkeypatch.setattr(settings, "database_url", database_url)
    test_engine = create_async_engine(async_database_url)
    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "AsyncSessionLocal", test_session_factory)
    monkeypatch.setattr(database, "async_session_factory", test_session_factory)
    config = _alembic_config()

    try:
        await asyncio.to_thread(command.upgrade, config, "0001_baseline")
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                "INSERT INTO users "
                "(id, email, hashed_password, full_name, role, is_active, is_verified, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("legacy-citizen", "old@example.test", "hashed", "Old Citizen", "citizen", 1, 1,
                 "2025-01-02 03:04:05", "2025-01-02 03:04:05"),
            )
            connection.execute(
                "INSERT INTO complaints "
                "(id, citizen_id, title, description, category, status, priority, severity, source, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("old-report", "legacy-citizen", "Old drain", "Drain blocked", "drainage", "pending",
                 "medium", 5, "web", "2025-01-02 03:04:05", "2025-01-02 03:04:05"),
            )
            connection.execute("DROP TABLE alembic_version")

        await database.init_db()
        with sqlite3.connect(database_path) as connection:
            version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
            link = connection.execute(
                "SELECT complaint_id, decision_source FROM report_links WHERE complaint_id = ?",
                ("old-report",),
            ).fetchone()
            media_columns = {row[1] for row in connection.execute("PRAGMA table_info(complaint_media)")}
            incident_columns = {row[1] for row in connection.execute("PRAGMA table_info(incidents)")}
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

        # Startup must adopt the latest migration head (tracking IDs follow Phase 7 hardening).
        assert version == ("0007_complaint_tracking_id",)
        assert link == ("old-report", "backfill")
        assert "perceptual_hash" in media_columns
        assert {"recurrence_of_incident_id", "location_accuracy_m", "priority"} <= incident_columns
        assert {
            "incident_timeline", "incident_notification_preferences", "notification_deliveries",
            "duplicate_review_cases", "duplicate_review_decisions",
        } <= tables
        complaint_columns = {row[1] for row in connection.execute("PRAGMA table_info(complaints)")}
        assert "idempotency_key" in complaint_columns
        assert "tracking_id" in complaint_columns
        backfilled = connection.execute(
            "SELECT tracking_id FROM complaints WHERE id = ?", ("old-report",)
        ).fetchone()
        assert backfilled is not None and backfilled[0].startswith("NC-")
    finally:
        await test_engine.dispose()
