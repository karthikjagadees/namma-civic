"""
Unit & Integration tests for Phase 7: SLA Monitoring & Autonomous Escalation Engine
"""
from datetime import datetime, timedelta, timezone
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import async_session_factory
from app.main import app
from app.models.complaint import Complaint, ComplaintStatus, PriorityLevel
from app.models.user import User, UserRole
from app.services.sla_service import SLAService


@pytest.mark.asyncio
async def test_sla_calculation_on_track():
    """Verify SLA calculation for newly created complaint."""
    complaint = Complaint(
        title="Recent Broken Manhole",
        description="Freshly reported issue",
        category="sanitation",
        priority=PriorityLevel.high,
        status=ComplaintStatus.pending,
        latitude=28.6139,
        longitude=77.2090,
        address="Central Plaza",
        created_at=datetime.now(timezone.utc) - timedelta(hours=2)
    )

    sla = SLAService.calculate_sla(complaint)
    assert sla["priority"] == "high"
    assert sla["total_sla_hours"] == 24
    assert sla["sla_status"] == "ON_TRACK"
    assert sla["risk_level"] == "LOW"
    assert sla["hours_remaining"] > 20


@pytest.mark.asyncio
async def test_sla_calculation_at_risk_and_breached():
    """Verify AT_RISK and BREACHED SLA classifications."""
    # At Risk: 20 hours into 24h SLA (> 75%)
    at_risk_complaint = Complaint(
        title="Deep Pothole",
        description="Needs repair soon",
        category="roads",
        priority=PriorityLevel.high,
        status=ComplaintStatus.assigned,
        latitude=28.6139,
        longitude=77.2090,
        address="Sector 4",
        created_at=datetime.now(timezone.utc) - timedelta(hours=20)
    )
    sla_risk = SLAService.calculate_sla(at_risk_complaint)
    assert sla_risk["sla_status"] == "AT_RISK"
    assert sla_risk["risk_level"] == "HIGH"

    # Breached: 30 hours into 24h SLA
    breached_complaint = Complaint(
        title="Overdue Pothole",
        description="Deadline passed",
        category="roads",
        priority=PriorityLevel.high,
        status=ComplaintStatus.in_progress,
        latitude=28.6139,
        longitude=77.2090,
        address="Sector 4",
        created_at=datetime.now(timezone.utc) - timedelta(hours=30)
    )
    sla_breach = SLAService.calculate_sla(breached_complaint)
    assert sla_breach["sla_status"] == "BREACHED"
    assert sla_breach["risk_level"] == "CRITICAL"


@pytest.mark.asyncio
async def test_sla_overview_api():
    """Test /api/sla/overview endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/sla/overview")
        assert res.status_code == 200
        data = res.json()
        assert "total_complaints" in data
        assert "on_track" in data
        assert "sla_compliance_rate" in data


@pytest.mark.asyncio
async def test_sla_auto_escalation_flow():
    """Test auto-escalation logic on an overdue complaint."""
    async with async_session_factory() as db:
        # Find or create a user for citizen_id
        res_user = await db.execute(select(User).limit(1))
        user = res_user.scalar_one_or_none()
        if not user:
            user = User(
                email="sla_citizen@example.com",
                full_name="SLA Citizen",
                hashed_password="fake",
                role=UserRole.citizen
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        # Create an overdue complaint
        complaint = Complaint(
            citizen_id=user.id,
            title="Overdue Water Pipeline Rupture",
            description="Flooding the lane for over 48 hours",
            category="water_leakage",
            priority=PriorityLevel.medium,
            status=ComplaintStatus.assigned,
            latitude=28.62,
            longitude=77.21,
            address="Lane 14",
            created_at=datetime.now(timezone.utc) - timedelta(hours=50) # Medium is 48h -> breached
        )
        db.add(complaint)
        await db.commit()
        await db.refresh(complaint)

        # Trigger auto escalation scan
        scan_res = await SLAService.scan_and_auto_escalate(db)
        assert scan_res["total_scanned"] >= 1
        assert scan_res["escalated_count"] >= 1

        repeated_scan = await SLAService.scan_and_auto_escalate(db)
        assert repeated_scan["escalated_count"] == 0

        # Check complaint priority bumped to high and timeline note added
        stmt = select(Complaint).where(Complaint.id == complaint.id)
        res = await db.execute(stmt)
        updated = res.scalar_one()
        assert updated.priority == PriorityLevel.high
