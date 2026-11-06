"""
Unit & Integration tests for Phase 8: Resolution Verification Engine
"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import async_session_factory
from app.main import app
from app.models.complaint import Complaint, ComplaintStatus, PriorityLevel
from app.models.user import User, UserRole
from app.services.verification_service import ResolutionVerificationService


@pytest.mark.asyncio
async def test_resolution_verification_success():
    """Verify successful before/after resolution with high confidence."""
    async with async_session_factory() as db:
        res_user = await db.execute(select(User).limit(1))
        user = res_user.scalar_one_or_none()
        if not user:
            user = User(
                email="worker@example.com",
                full_name="Maintenance Worker",
                hashed_password="fake",
                role=UserRole.officer
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        complaint = Complaint(
            citizen_id=user.id,
            title="Broken Traffic Light Junction 9",
            description="Signal stuck on yellow causing gridlock",
            category="traffic_signal",
            priority=PriorityLevel.high,
            status=ComplaintStatus.in_progress,
            latitude=28.6139,
            longitude=77.2090,
            address="Junction 9 Ring Road"
        )
        db.add(complaint)
        await db.commit()
        await db.refresh(complaint)

        res = await ResolutionVerificationService.verify_resolution_evidence(
            session=db,
            complaint_id=str(complaint.id),
            resolution_notes="Traffic controller motherboard replaced and optical sensors calibrated. Fully functional.",
            resolution_image_url="/uploads/repaired_traffic_signal.jpg",
            officer_id=user.id
        )

        assert res["new_status"] == "resolved"
        assert res["verification"]["verified"] is True
        assert res["verification"]["confidence_score"] >= 0.90
        assert res["verification"]["defect_clearance_detected"] is True
        assert res["resolved_at"] is not None


@pytest.mark.asyncio
async def test_resolution_verification_failure():
    """Verify rejection when repair notes indicate incomplete work."""
    async with async_session_factory() as db:
        res_user = await db.execute(select(User).limit(1))
        user = res_user.scalar_one()

        complaint = Complaint(
            citizen_id=user.id,
            title="Sewer Clog",
            description="Overflow on pavement",
            category="drainage",
            priority=PriorityLevel.medium,
            status=ComplaintStatus.assigned,
            latitude=28.6139,
            longitude=77.2090,
            address="Lane 5"
        )
        db.add(complaint)
        await db.commit()
        await db.refresh(complaint)

        res = await ResolutionVerificationService.verify_resolution_evidence(
            session=db,
            complaint_id=str(complaint.id),
            resolution_notes="Inspected site but pending materials to complete suction pump repair. Incomplete.",
            resolution_image_url=None,
        )

        assert res["verification"]["verified"] is False
        assert res["verification"]["verification_status"] == "VERIFICATION_FAILED"
        assert res["new_status"] != "resolved"


@pytest.mark.asyncio
async def test_resolution_api_endpoint():
    """Test POST /api/resolution/verify/{complaint_id} endpoint."""
    async with async_session_factory() as db:
        res_user = await db.execute(select(User).limit(1))
        user = res_user.scalar_one()

        complaint = Complaint(
            citizen_id=user.id,
            title="Pothole Near Bus Stand",
            description="Hazardous pothole",
            category="pothole",
            priority=PriorityLevel.medium,
            status=ComplaintStatus.in_progress,
            latitude=28.6139,
            longitude=77.2090,
            address="Bus Stand 3"
        )
        db.add(complaint)
        await db.commit()
        await db.refresh(complaint)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            login = await ac.post("/api/auth/login", json={
                "email": "officer@demo.namma-civic.ai", "password": "password123",
            })
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            res = await ac.post(f"/api/resolution/verify/{complaint.id}", json={
                "resolution_notes": "Filled with bitumen asphalt and leveled with compactor roller.",
                "resolution_image_url": "/uploads/resolved_pothole.jpg"
            }, headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["new_status"] == "resolved"
            assert data["verification"]["confidence_score"] > 0.8
