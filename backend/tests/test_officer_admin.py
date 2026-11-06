"""
Unit & Integration tests for Officer Tactical Command & Admin Control Modules
"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.security import create_access_token
from app.main import app
from app.models.complaint import Complaint, ComplaintStatus, PriorityLevel
from app.models.department import Department
from app.models.incident import Incident, IncidentStatus
from app.models.report_link import ReportLink, ReportLinkDecisionSource
from app.models.user import User, UserRole
from app.services.admin_service import AdminService
from app.services.officer_service import OfficerService


@pytest.mark.asyncio
async def test_department_officer_queue_includes_unrouted_reports_for_triage():
    """New reports without a department should remain visible to duty officers."""
    async with async_session_factory() as db:
        department = await db.scalar(select(Department).where(Department.code == "ROADS"))
        citizen = User(
            email="unrouted_reporter@namma-civic.ai",
            full_name="Unrouted Reporter",
            hashed_password="fake",
            role=UserRole.citizen,
        )
        officer = User(
            email="unrouted_triage_officer@namma-civic.ai",
            full_name="Unrouted Triage Officer",
            hashed_password="fake",
            role=UserRole.officer,
            department_id=department.id,
        )
        db.add_all([citizen, officer])
        await db.flush()
        complaint = Complaint(
            citizen_id=citizen.id,
            title="Unrouted pothole report",
            description="A new report still waiting for automatic routing.",
            category="pothole",
            status=ComplaintStatus.pending,
            priority=PriorityLevel.medium,
        )
        db.add(complaint)
        await db.commit()

        queue = await OfficerService.get_officer_queue(
            session=db,
            officer_id=str(officer.id),
            department_id=str(department.id),
        )

        assert any(item["id"] == str(complaint.id) for item in queue)


@pytest.mark.asyncio
async def test_officer_queue_groups_linked_reports_and_counts_distinct_citizens():
    """One shared issue appears once in the queue with its independent reporters."""
    async with async_session_factory() as db:
        department = await db.scalar(select(Department).where(Department.code == "ROADS"))
        officer = User(
            email="incident_grouping_officer@namma-civic.ai",
            full_name="Incident Grouping Officer",
            hashed_password="fake",
            role=UserRole.officer,
            department_id=department.id,
        )
        reporters = [
            User(email=f"incident_reporter_{idx}@namma-civic.ai", full_name=f"Reporter {idx}",
                 hashed_password="fake", role=UserRole.citizen)
            for idx in (1, 2)
        ]
        db.add_all([officer, *reporters])
        await db.flush()
        incident = Incident(
            title="Broken street light",
            category="street_light",
            status=IncidentStatus.open,
            priority="medium",
            latitude=12.9,
            longitude=77.5,
        )
        db.add(incident)
        await db.flush()
        reports = [
            Complaint(
                citizen_id=reporter.id,
                title="Broken street light",
                description=f"Light is out, report {idx}",
                category="street_light",
                status=ComplaintStatus.pending,
                priority=PriorityLevel.medium,
                assigned_officer_id=officer.id,
            )
            for idx, reporter in enumerate(reporters, start=1)
        ]
        db.add_all(reports)
        await db.flush()
        db.add_all([
            ReportLink(
                complaint_id=report.id,
                incident_id=incident.id,
                decision_source=ReportLinkDecisionSource.auto,
                is_active=True,
            )
            for report in reports
        ])
        await db.commit()

        queue = await OfficerService.get_officer_queue(session=db, officer_id=str(officer.id))
        grouped = [item for item in queue if item.get("incident_id") == str(incident.id)]

        assert len(grouped) == 1
        assert grouped[0]["report_count"] == 2
        assert grouped[0]["reporter_count"] == 2


@pytest.mark.asyncio
async def test_officer_service_queue_and_stats():
    """Verify officer queue sorting and workload calculations."""
    async with async_session_factory() as db:
        # Fetch or create officer
        res_officer = await db.execute(select(User).where(User.role == UserRole.officer).limit(1))
        officer = res_officer.scalar_one_or_none()
        if not officer:
            officer = User(
                email="officer_test@namma-civic.ai",
                full_name="Officer Test",
                hashed_password="fake",
                role=UserRole.officer
            )
            db.add(officer)
            await db.commit()
            await db.refresh(officer)

        # Create a test complaint assigned to this officer
        comp = Complaint(
            citizen_id=officer.id,
            title="Broken Traffic Pole",
            description="Lying in street",
            category="traffic_signal",
            status=ComplaintStatus.assigned,
            priority=PriorityLevel.critical,
            assigned_officer_id=officer.id,
        )
        db.add(comp)
        await db.commit()

        queue = await OfficerService.get_officer_queue(session=db, officer_id=officer.id)
        assert len(queue) >= 1
        assert any(item["id"] == str(comp.id) for item in queue)
        assert "sla" in queue[0]

        stats = await OfficerService.get_officer_workload_stats(session=db, officer_id=officer.id)
        assert stats["total_cases"] >= 1
        assert "active_cases" in stats
        assert "compliance_rate" in stats


@pytest.mark.asyncio
async def test_admin_service_users_and_metrics():
    """Verify admin user listing, updating, and system telemetry."""
    async with async_session_factory() as db:
        users = await AdminService.list_users(session=db, limit=10)
        assert "total" in users
        assert len(users["items"]) >= 1

        # Test updating user status
        target_user = users["items"][0]
        updated = await AdminService.update_user(
            session=db,
            user_id=target_user["id"],
            role="officer"
        )
        assert updated["role"] == "officer"

        # System health metrics
        metrics = await AdminService.get_system_health_metrics(session=db)
        assert metrics["system_name"] == "Namma Civic Autonomous Engine"
        assert metrics["mcp_server_status"] == "ONLINE"
        assert "metrics" in metrics


@pytest.mark.asyncio
async def test_officer_and_admin_api_endpoints_rbac():
    """Verify endpoint responses and RBAC security gates."""
    async with async_session_factory() as db:
        # Create or fetch officer, admin, and citizen
        res_admin = await db.execute(select(User).where(User.role == UserRole.admin).limit(1))
        admin_user = res_admin.scalar_one_or_none()
        if not admin_user:
            admin_user = User(email="super_admin@namma-civic.ai", full_name="Admin", hashed_password="fake", role=UserRole.admin)
            db.add(admin_user)

        res_citizen = await db.execute(select(User).where(User.role == UserRole.citizen).limit(1))
        citizen_user = res_citizen.scalar_one_or_none()
        if not citizen_user:
            citizen_user = User(email="plain_citizen@namma-civic.ai", full_name="Citizen", hashed_password="fake", role=UserRole.citizen)
            db.add(citizen_user)

        await db.commit()
        await db.refresh(admin_user)
        await db.refresh(citizen_user)

        admin_token = create_access_token(admin_user.id, role="admin")
        citizen_token = create_access_token(citizen_user.id, role="citizen")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Citizen should be blocked from /api/admin/users (403)
            r_forbidden = await ac.get("/api/admin/users", headers={"Authorization": f"Bearer {citizen_token}"})
            assert r_forbidden.status_code == 403

            # Admin should have full access to /api/admin/users (200)
            r_admin = await ac.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
            assert r_admin.status_code == 200
            assert "items" in r_admin.json()

            # Admin gets system metrics (200)
            r_sys = await ac.get("/api/admin/system/metrics", headers={"Authorization": f"Bearer {admin_token}"})
            assert r_sys.status_code == 200
            assert r_sys.json()["mcp_tools_active"] >= 8

            # Officer queue endpoint test with admin (admin has officer privilege)
            r_queue = await ac.get("/api/officer/queue", headers={"Authorization": f"Bearer {admin_token}"})
            assert r_queue.status_code == 200
            assert isinstance(r_queue.json(), list)
