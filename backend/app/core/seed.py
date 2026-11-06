"""
Namma Civic — Database Seeding
Seeds demo accounts, civic departments, and realistic sample complaints with AI telemetry and SLA tracking.
Ensures the local SQLite database is 100% loaded and operational out-of-the-box.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.ai_analysis import AIAnalysis
from app.models.complaint import (
    Complaint,
    ComplaintCategory,
    ComplaintMedia,
    ComplaintSource,
    ComplaintStatus,
    ComplaintTimeline,
    MediaType,
    PriorityLevel,
)
from app.models.department import Department
from app.models.user import User, UserRole

logger = get_logger(__name__)

DEMO_DEPARTMENTS = [
    {
        "code": "ROADS",
        "name": "Roads & Infrastructure",
        "description": "Potholes, road damage, footpaths, road signage, and traffic markings.",
        "sla_hours_default": 48,
        "email": "roads@namma-civic.ai",
        "phone": "+919876543220",
    },
    {
        "code": "SANITATION",
        "name": "Sanitation & Solid Waste",
        "description": "Garbage dumps, missed trash collection, public bin overflows, and street sweeping.",
        "sla_hours_default": 24,
        "email": "sanitation@namma-civic.ai",
        "phone": "+919876543221",
    },
    {
        "code": "WATER",
        "name": "Water Supply & Sewage",
        "description": "Pipeline leaks, water contamination, low pressure, and sewage overflow.",
        "sla_hours_default": 24,
        "email": "water@namma-civic.ai",
        "phone": "+919876543222",
    },
    {
        "code": "ELECTRICAL",
        "name": "Electricity & Street Lighting",
        "description": "Faulty street lights, hanging cables, dark stretches, and transformer issues.",
        "sla_hours_default": 24,
        "email": "electrical@namma-civic.ai",
        "phone": "+919876543223",
    },
    {
        "code": "DRAINAGE",
        "name": "Drainage & Flood Control",
        "description": "Clogged storm drains, stagnant water, open manholes, and monsoon flooding.",
        "sla_hours_default": 36,
        "email": "drainage@namma-civic.ai",
        "phone": "+919876543224",
    },
    {
        "code": "PUBLIC_WORKS",
        "name": "Public Works & Maintenance",
        "description": "Park maintenance, broken benches, encroachment, and public property repairs.",
        "sla_hours_default": 72,
        "email": "publicworks@namma-civic.ai",
        "phone": "+919876543225",
    },
]

DEMO_USERS = [
    {
        "email": "citizen@demo.namma-civic.ai",
        "password": "password123",
        "full_name": "Demo Citizen",
        "role": UserRole.citizen,
        "phone": "+919876543210",
        "is_verified": True,
    },
    {
        "email": "officer@demo.namma-civic.ai",
        "password": "password123",
        "full_name": "Officer Sarah Chen (Roads)",
        "role": UserRole.officer,
        "dept_code": "ROADS",
        "phone": "+919876543211",
        "is_verified": True,
    },
    {
        "email": "water.officer@demo.namma-civic.ai",
        "password": "password123",
        "full_name": "Officer Marcus Vance (Water)",
        "role": UserRole.officer,
        "dept_code": "WATER",
        "phone": "+919876543213",
        "is_verified": True,
    },
    {
        "email": "sanitation.officer@demo.namma-civic.ai",
        "password": "password123",
        "full_name": "Officer Priya Sharma (Sanitation)",
        "role": UserRole.officer,
        "dept_code": "SANITATION",
        "phone": "+919876543214",
        "is_verified": True,
    },
    {
        "email": "power.officer@demo.namma-civic.ai",
        "password": "password123",
        "full_name": "Officer David Kalu (Electrical)",
        "role": UserRole.officer,
        "dept_code": "ELECTRICAL",
        "phone": "+919876543215",
        "is_verified": True,
    },
    {
        "email": "admin@demo.namma-civic.ai",
        "password": "password123",
        "full_name": "Demo Administrator",
        "role": UserRole.admin,
        "phone": "+919876543212",
        "is_verified": True,
    },
]


def _previous_email(email: str) -> str | None:
    """Address this record used before the project was renamed to Namma Civic.

    Existing databases still have the old domain. Startup rewrites those rows
    so the demo buttons and department contacts keep matching.
    """
    if email.endswith("@demo.namma-civic.ai"):
        return email[: -len("@demo.namma-civic.ai")] + "@demo.civicfix.ai"
    if email.endswith("@namma-civic.ai"):
        return email[: -len("@namma-civic.ai")] + "@civicfix.ai"
    return None


async def seed_departments(session: AsyncSession) -> None:
    """Seed standard civic departments if they do not already exist."""
    for dept_data in DEMO_DEPARTMENTS:
        result = await session.execute(
            select(Department).where(Department.code == dept_data["code"])
        )
        existing = result.scalar_one_or_none()
        if existing and existing.email == _previous_email(dept_data["email"]):
            existing.email = dept_data["email"]
        if not existing:
            dept = Department(
                code=dept_data["code"],
                name=dept_data["name"],
                description=dept_data["description"],
                sla_hours_default=dept_data["sla_hours_default"],
                email=dept_data["email"],
                phone=dept_data["phone"],
                is_active=True,
            )
            session.add(dept)
            logger.info("Created department", code=dept.code, name=dept.name)
    await session.flush()


async def seed_demo_users(session: AsyncSession) -> None:
    """Seed standard demo users if they do not already exist and associate departments."""
    dept_res = await session.execute(select(Department))
    dept_map = {d.code: d.id for d in dept_res.scalars().all()}

    for user_data in DEMO_USERS:
        result = await session.execute(
            select(User).where(User.email == user_data["email"])
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            previous = _previous_email(user_data["email"])
            if previous:
                legacy = await session.execute(select(User).where(User.email == previous))
                existing = legacy.scalar_one_or_none()
                if existing is not None:
                    existing.email = user_data["email"]
        target_dept_id = dept_map.get(user_data.get("dept_code")) if user_data.get("dept_code") else None

        if not existing:
            user = User(
                email=user_data["email"],
                hashed_password=hash_password(user_data["password"]),
                full_name=user_data["full_name"],
                phone=user_data.get("phone"),
                role=user_data["role"],
                is_active=True,
                is_verified=user_data.get("is_verified", True),
                department_id=target_dept_id,
            )
            session.add(user)
            logger.info("Created demo user", email=user.email, role=user.role.value, dept=user_data.get("dept_code"))
        else:
            if user_data.get("full_name") and existing.full_name != user_data["full_name"]:
                existing.full_name = user_data["full_name"]
            if target_dept_id and existing.department_id != target_dept_id:
                existing.department_id = target_dept_id
            existing.hashed_password = hash_password(user_data["password"])
    await session.flush()


async def seed_demo_complaints(session: AsyncSession) -> None:
    """Seed sample civic complaints with rich AI analysis, media, and timeline events."""
    count_res = await session.execute(select(func.count(Complaint.id)))
    existing_count = count_res.scalar() or 0
    if existing_count >= 5:
        logger.info(f"Database already has {existing_count} complaints. Skipping complaint seed.")
        return

    # Fetch users
    citizen_res = await session.execute(select(User).where(User.email == "citizen@demo.namma-civic.ai"))
    citizen = citizen_res.scalar_one_or_none()
    if not citizen:
        return

    officer_res = await session.execute(select(User).where(User.email == "officer@demo.namma-civic.ai"))
    officer = officer_res.scalar_one_or_none()

    # Fetch departments map
    depts_res = await session.execute(select(Department))
    dept_map = {d.code: d.id for d in depts_res.scalars().all()}

    now = datetime.now(timezone.utc)

    SAMPLE_CASES = [
        {
            "title": "Severe Pothole Cluster & Caving Asphalt on 100ft Ring Road",
            "description": "Deep asphalt depression causing serious vehicular swerving near the junction. Two two-wheelers reportedly skidded yesterday evening.",
            "category": ComplaintCategory.pothole,
            "status": ComplaintStatus.in_progress,
            "priority": PriorityLevel.high,
            "severity": 7,
            "address": "100ft Inner Ring Road, Indiranagar, Bengaluru",
            "landmark": "Opposite Domlur Flyover exit",
            "lat": 12.9647,
            "lng": 77.6433,
            "dept_code": "ROADS",
            "assign_officer": True,
            "created_hours_ago": 6,
            "ai": {
                "summary": "Deep asphalt depression posing immediate collision hazard to two-wheelers.",
                "detected_cat": "ROADS",
                "conf": 0.96,
                "urgency": 0.82,
                "sev": 7,
                "dept": "Roads & Infrastructure",
                "reasoning": "Vision model identified 45cm diameter crater with fractured base layer. High traffic corridor warrants priority response.",
                "entities": {"location_mentions": ["100ft Ring Road", "Domlur Flyover"], "hazard_type": "deep road crater"},
            },
        },
        {
            "title": "Overflowing Public Dump & Solid Waste Blockage",
            "description": "Community garbage bin has not been cleared for 4 days. Waste spilled over onto the pedestrian walkway creating foul odor and health hazard.",
            "category": ComplaintCategory.garbage,
            "status": ComplaintStatus.verified,
            "priority": PriorityLevel.medium,
            "severity": 5,
            "address": "8th Cross, Commercial Street, Tasker Town, Bengaluru",
            "landmark": "Near Government High School",
            "lat": 12.9822,
            "lng": 77.6083,
            "dept_code": "SANITATION",
            "assign_officer": False,
            "created_hours_ago": 18,
            "ai": {
                "summary": "Municipal waste overflow obstructing pedestrian access and creating biological hazard.",
                "detected_cat": "SANITATION",
                "conf": 0.94,
                "urgency": 0.60,
                "sev": 5,
                "dept": "Sanitation & Solid Waste",
                "reasoning": "Uncollected organic and plastic debris detected. High density commercial market area.",
                "entities": {"location_mentions": ["Commercial Street"], "hazard_type": "solid waste overflow"},
            },
        },
        {
            "title": "High-Pressure Water Main Burst & Road Flooding",
            "description": "Major underground supply pipeline ruptured. Clean drinking water gushing at high velocity flooding entire crossroad and disrupting supply to ~500 homes.",
            "category": ComplaintCategory.water_leakage,
            "status": ComplaintStatus.assigned,
            "priority": PriorityLevel.critical,
            "severity": 9,
            "address": "5th Cross, Malleshwaram, Bengaluru",
            "landmark": "Behind Malleshwaram Circle",
            "lat": 12.9984,
            "lng": 77.5704,
            "dept_code": "WATER",
            "assign_officer": False,
            "created_hours_ago": 26, # SLA breached or at risk
            "ai": {
                "summary": "High velocity water main breach resulting in massive potable water loss and road flooding.",
                "detected_cat": "WATER",
                "conf": 0.98,
                "urgency": 0.95,
                "sev": 9,
                "dept": "Water Supply & Sewage",
                "reasoning": "Critical pipeline rupture. High volume loss and structural erosion risk to adjacent roadway.",
                "entities": {"location_mentions": ["5th Cross, Malleshwaram"], "hazard_type": "water main rupture"},
            },
        },
        {
            "title": "Streetlight Grid Outage Across 14th Main",
            "description": "Over 12 consecutive sodium streetlights completely dark for the past 3 nights. Zone is pitch black and dangerous for pedestrians.",
            "category": ComplaintCategory.street_light,
            "status": ComplaintStatus.resolved,
            "priority": PriorityLevel.medium,
            "severity": 4,
            "address": "14th Main, HSR Layout Sector 2, Bengaluru",
            "landmark": "Sector 2 Neighborhood Park",
            "lat": 12.9116,
            "lng": 77.6389,
            "dept_code": "ELECTRICAL",
            "assign_officer": False,
            "created_hours_ago": 72,
            "resolved_hours_ago": 12,
            "ai": {
                "summary": "Grid-level circuit trip causing multi-lamp failure along 400m residential arterial road.",
                "detected_cat": "ELECTRICAL",
                "conf": 0.95,
                "urgency": 0.50,
                "sev": 4,
                "dept": "Electricity & Street Lighting",
                "reasoning": "Sequential luminaire blackout suggests feeder line or timer breaker issue.",
                "entities": {"location_mentions": ["14th Main, HSR Layout"], "hazard_type": "lighting blackout"},
            },
        },
        {
            "title": "Clogged Stormwater Drain & Waterlogging Risk",
            "description": "Pre-monsoon silt and plastic waste completely blocking drainage outlet. Even a short 15-minute shower results in knee-deep waterlogging.",
            "category": ComplaintCategory.drainage,
            "status": ComplaintStatus.analyzing,
            "priority": PriorityLevel.high,
            "severity": 8,
            "address": "Bellandur Outer Ring Road, Bengaluru",
            "landmark": "Near EcoSpace Tech Park Entrance",
            "lat": 12.9260,
            "lng": 77.6762,
            "dept_code": "DRAINAGE",
            "assign_officer": False,
            "created_hours_ago": 2,
            "ai": {
                "summary": "Primary storm sewer inlet choked with dense plastic accumulation.",
                "detected_cat": "DRAINAGE",
                "conf": 0.92,
                "urgency": 0.78,
                "sev": 8,
                "dept": "Drainage & Flood Control",
                "reasoning": "High flood vulnerability index corridor. Requires suction desilting truck deployment.",
                "entities": {"location_mentions": ["Bellandur ORR", "EcoSpace"], "hazard_type": "storm drain blockage"},
            },
        },
        {
            "title": "Illegal Construction Encroachment on Pedestrian Footpath",
            "description": "Heavy scaffolding and construction debris dumped onto public footpath forcing schoolchildren and elderly pedestrians into heavy moving traffic.",
            "category": ComplaintCategory.encroachment,
            "status": ComplaintStatus.pending,
            "priority": PriorityLevel.low,
            "severity": 3,
            "address": "12th Main Road, Koramangala 4th Block, Bengaluru",
            "landmark": "Adjacent to Sony World Signal",
            "lat": 12.9345,
            "lng": 77.6245,
            "dept_code": "PUBLIC_WORKS",
            "assign_officer": False,
            "created_hours_ago": 3,
            "ai": {
                "summary": "Unauthorized building material staging on pedestrian right-of-way.",
                "detected_cat": "PUBLIC_WORKS",
                "conf": 0.89,
                "urgency": 0.40,
                "sev": 3,
                "dept": "Public Works & Maintenance",
                "reasoning": "Public walkway obstruction. Low immediate structural danger but violates municipal zoning.",
                "entities": {"location_mentions": ["Koramangala 4th Block"], "hazard_type": "footpath obstruction"},
            },
        },
        {
            "title": "Secondary Asphalt Trenching Damage",
            "description": "Unpaved utility cut across roadway after cable laying work was left without asphalt restoration.",
            "category": ComplaintCategory.pothole,
            "status": ComplaintStatus.in_progress,
            "priority": PriorityLevel.high,
            "severity": 6,
            "address": "100ft Ring Road, Indiranagar, Bengaluru",
            "landmark": "Near Indiranagar Metro Station",
            "lat": 12.9719,
            "lng": 77.6412,
            "dept_code": "ROADS",
            "assign_officer": True,
            "created_hours_ago": 12,
            "ai": {
                "summary": "Unrestored cross-trench across multi-lane arterial road.",
                "detected_cat": "ROADS",
                "conf": 0.94,
                "urgency": 0.70,
                "sev": 6,
                "dept": "Roads & Infrastructure",
                "reasoning": "Utility reinstatement violation. High potential for vehicle axle damage.",
                "entities": {"location_mentions": ["100ft Ring Road"], "hazard_type": "unpaved utility trench"},
            },
        },
    ]

    for item in SAMPLE_CASES:
        created_time = now - timedelta(hours=item["created_hours_ago"])
        resolved_time = now - timedelta(hours=item["resolved_hours_ago"]) if "resolved_hours_ago" in item else None

        complaint = Complaint(
            id=str(uuid.uuid4()),
            citizen_id=citizen.id,
            title=item["title"],
            description=item["description"],
            category=item["category"],
            status=item["status"],
            priority=item["priority"],
            severity=item["severity"],
            latitude=item["lat"],
            longitude=item["lng"],
            address=item["address"],
            landmark=item.get("landmark"),
            department_id=dept_map.get(item["dept_code"]),
            assigned_officer_id=officer.id if item.get("assign_officer") and officer else None,
            source=ComplaintSource.web,
            created_at=created_time,
            updated_at=created_time,
            resolved_at=resolved_time,
        )
        session.add(complaint)
        await session.flush()

        # Keep demo reports consistent with citizen-submitted reports: every
        # complaint has one active incident association from creation.
        from app.services.incident_service import create_initial_incident_for_report
        await create_initial_incident_for_report(session, complaint)

        # Add Complaint Media
        media_item = ComplaintMedia(
            complaint_id=complaint.id,
            media_type=MediaType.image,
            file_url="https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?auto=format&fit=crop&w=800&q=80",
            file_name="evidence_photo.jpg",
            file_size=102400,
            mime_type="image/jpeg",
            caption="Citizen uploaded evidence photo",
            created_at=created_time,
        )
        session.add(media_item)

        # Add AI Analysis Record
        ai_data = item["ai"]
        ai_analysis = AIAnalysis(
            complaint_id=complaint.id,
            summary=ai_data["summary"],
            detected_category=ai_data["detected_cat"],
            confidence_score=ai_data["conf"],
            urgency_score=ai_data["urgency"],
            severity=ai_data["sev"],
            recommended_department=ai_data["dept"],
            reasoning=ai_data["reasoning"],
            extracted_entities=ai_data["entities"],
            provider_used="groq",
            model_used="llama-3.3-70b-versatile",
            processing_time_ms=184,
            created_at=created_time + timedelta(seconds=2),
            updated_at=created_time + timedelta(seconds=2),
        )
        session.add(ai_analysis)

        # Add Complaint Timeline Audit Entries
        t1 = ComplaintTimeline(
            complaint_id=complaint.id,
            status=ComplaintStatus.pending,
            changed_by_id=citizen.id,
            note="Incident reported by citizen through Namma Civic web portal.",
            created_at=created_time,
        )
        session.add(t1)

        t2 = ComplaintTimeline(
            complaint_id=complaint.id,
            status=ComplaintStatus.verified,
            note="Autonomous Groq LPU Multimodal AI verified incident severity and recommended routing.",
            created_at=created_time + timedelta(seconds=3),
        )
        session.add(t2)

        if item["status"] in [ComplaintStatus.assigned, ComplaintStatus.in_progress, ComplaintStatus.resolved]:
            t3 = ComplaintTimeline(
                complaint_id=complaint.id,
                status=ComplaintStatus.assigned,
                changed_by_id=officer.id if officer else None,
                note=f"Assigned to {item['dept_code']} field operations.",
                created_at=created_time + timedelta(minutes=30),
            )
            session.add(t3)

        if item["status"] in [ComplaintStatus.in_progress, ComplaintStatus.resolved]:
            t4 = ComplaintTimeline(
                complaint_id=complaint.id,
                status=ComplaintStatus.in_progress,
                changed_by_id=officer.id if officer else None,
                note="Field crew deployed to site with standard work order.",
                created_at=created_time + timedelta(hours=1),
            )
            session.add(t4)

        if item["status"] == ComplaintStatus.resolved and resolved_time:
            t5 = ComplaintTimeline(
                complaint_id=complaint.id,
                status=ComplaintStatus.resolved,
                changed_by_id=officer.id if officer else None,
                note="Resolution verified. Repair work completed and validated.",
                created_at=resolved_time,
            )
            session.add(t5)

    await session.flush()
    logger.info("Successfully seeded realistic civic complaints, AI analyses, and SLA timelines.")


async def seed_all(session: AsyncSession) -> None:
    """Seed departments, demo accounts, and sample civic complaints."""
    await seed_departments(session)
    await seed_demo_users(session)
    await seed_demo_complaints(session)
