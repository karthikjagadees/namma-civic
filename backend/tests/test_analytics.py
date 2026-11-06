"""
Unit and Integration tests for Phase 9: Civic Hotspots & Geospatial Analytics
"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import async_session_factory
from app.main import app
from app.models.complaint import Complaint, ComplaintStatus, PriorityLevel
from app.models.user import User, UserRole
from app.services.analytics_service import AnalyticsService, haversine_distance_m


def test_haversine_distance_computation():
    """Verify haversine formula distance accuracy."""
    # Central Plaza to 500m north roughly
    d = haversine_distance_m(28.6139, 77.2090, 28.6184, 77.2090)
    assert 480 <= d <= 520


@pytest.mark.asyncio
async def test_analytics_summary_api():
    """Test GET /api/analytics/summary endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/analytics/summary")
        assert res.status_code == 200
        data = res.json()
        assert "civic_health_index" in data
        assert "status_rating" in data
        assert "total_grievances" in data
        assert 0 <= data["civic_health_index"] <= 100


@pytest.mark.asyncio
async def test_geospatial_hotspot_clustering():
    """Test clustering of multiple nearby defects into a chronic defect zone."""
    async with async_session_factory() as db:
        res_user = await db.execute(select(User).limit(1))
        user = res_user.scalar_one_or_none()
        if not user:
            user = User(
                email="geo_user@example.com",
                full_name="Geo User",
                hashed_password="fake",
                role=UserRole.citizen
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        # Create two complaints 80 meters apart (same hotspot cluster)
        c1 = Complaint(
            citizen_id=user.id,
            title="Pothole Cluster Point A",
            description="Deep crater near market entrance",
            category="pothole",
            priority=PriorityLevel.high,
            status=ComplaintStatus.assigned,
            latitude=28.6300,
            longitude=77.2200,
            address="Market Gate 1"
        )
        c2 = Complaint(
            citizen_id=user.id,
            title="Pothole Cluster Point B",
            description="Broken asphalt near market exit",
            category="pothole",
            priority=PriorityLevel.high,
            status=ComplaintStatus.in_progress,
            latitude=28.6305,
            longitude=77.2205,
            address="Market Gate 2"
        )
        db.add_all([c1, c2])
        await db.commit()

        clusters = await AnalyticsService.get_geospatial_hotspots(db, cluster_radius_m=300.0)
        assert len(clusters) >= 1
        # Find cluster that includes our points
        pothole_clusters = [cl for cl in clusters if cl["primary_category"] == "pothole"]
        assert len(pothole_clusters) >= 1
        assert pothole_clusters[0]["incident_count"] >= 2


@pytest.mark.asyncio
async def test_department_scorecard_api():
    """Test GET /api/analytics/departments endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/analytics/departments")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        if len(data) > 0:
            dept = data[0]
            assert "name" in dept
            assert "efficiency_score" in dept
            assert "sla_compliance_rate" in dept
