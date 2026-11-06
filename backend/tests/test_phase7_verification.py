"""Phase 7 end-to-end, privacy, idempotency, and failure-boundary tests."""
from __future__ import annotations

import uuid
from io import BytesIO

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.database import async_session_factory
from app.models.complaint import (
    Complaint, ComplaintCategory, ComplaintMedia, ComplaintSource, ComplaintStatus, MediaType, PriorityLevel,
)
from app.models.follow_up import NotificationDelivery
from app.models.incident import Incident
from app.models.report_link import ReportLink
from app.models.user import User, UserRole
from app.models.work_order import WorkOrder


BASE = "http://test"


async def _register(client: AsyncClient, name: str) -> tuple[str, str]:
    """Register a unique synthetic citizen and return its ID and bearer token."""
    suffix = uuid.uuid4().hex
    response = await client.post("/api/auth/register", json={
        "email": f"{name}-{suffix}@example.org",
        "password": "securepass1",
        "full_name": name,
        "phone": f"+1555{suffix[:7]}",
    })
    assert response.status_code == 201, response.text
    data = response.json()
    return data["user"]["id"], data["access_token"]


@pytest.mark.asyncio
async def test_three_same_location_same_photo_reports_become_one_higher_priority_incident(monkeypatch):
    """Identical location/photo evidence links varied text and boosts incident SLA once."""
    from app.mcp.client import mcp_client
    from app.services.agent_service import AgentService
    from app.services.incident_service import create_initial_incident_for_report
    from app.services.officer_service import OfficerService
    from app.services.sla_service import SLAService
    from app.schemas.agent import OfficerApprovalRequest

    async def offline_tool(name, arguments):
        if name == "civic_work_order_dispatch":
            return {"work_order_id": "WO-SAME-LOCATION-SYNTHETIC", "status": "DISPATCHED"}
        return {"delivery_id": f"SAME-LOCATION-{uuid.uuid4().hex[:8]}", "status": "DELIVERED"}

    monkeypatch.setattr(mcp_client, "call_tool", offline_tool)
    descriptions = (
        "Street lamp is broken; this corner is very dark after sunset.",
        "No light near the junction, people are struggling to walk here.",
        "The same pole is not working and vehicles cannot see pedestrians.",
    )
    channels = (ComplaintSource.web, ComplaintSource.mobile, ComplaintSource.whatsapp)
    complaint_ids: list[str] = []
    provisional_ids: list[str] = []
    results = []
    async with async_session_factory() as session:
        officer = User(
            email=f"same-location-officer-{uuid.uuid4().hex}@test.invalid",
            hashed_password="unused",
            full_name="Synthetic review officer",
            role=UserRole.officer,
        )
        session.add(officer)
        await session.commit()
        officer_id = officer.id

    for index, (description, channel) in enumerate(zip(descriptions, channels), start=1):
        async with async_session_factory() as session:
            suffix = uuid.uuid4().hex
            citizen = User(
                email=f"same-location-citizen-{suffix}@test.invalid",
                hashed_password="unused",
                full_name=f"Same location reporter {index}",
                role=UserRole.citizen,
            )
            session.add(citizen)
            await session.flush()
            complaint = Complaint(
                citizen_id=citizen.id,
                title="Street light not working",
                description=description,
                category=ComplaintCategory.street_light,
                status=ComplaintStatus.pending,
                priority=PriorityLevel.medium,
                latitude=12.9716,
                longitude=77.5946,
                address="Synthetic Junction Road",
                landmark="Synthetic Junction",
                source=channel,
            )
            session.add(complaint)
            await session.flush()
            session.add(ComplaintMedia(
                complaint_id=complaint.id,
                media_type=MediaType.image,
                file_url=f"/uploads/same-location-{index}.png",
                file_name=f"same-location-{index}.png",
                mime_type="image/png",
                perceptual_hash="7f7f7f7f7f7f7f7f",
            ))
            incident, _link = await create_initial_incident_for_report(session, complaint)
            complaint_ids.append(complaint.id)
            provisional_ids.append(incident.id)
            await session.commit()

        async with async_session_factory() as session:
            result = await AgentService.orchestrate_complaint(complaint.id, session)
        if result.get("is_awaiting_approval"):
            async with async_session_factory() as session:
                result = await AgentService.submit_human_decision(
                    complaint_id=complaint.id,
                    approval_req=OfficerApprovalRequest(approved=True, officer_notes="Synthetic verification approval"),
                    officer_id=officer_id,
                    session=session,
                )
        results.append(result)

    async with async_session_factory() as session:
        active_links = list((await session.scalars(select(ReportLink).where(
            ReportLink.complaint_id.in_(complaint_ids), ReportLink.is_active.is_(True),
        ))).all())
        canonical_ids = {link.incident_id for link in active_links}
        incidents = list((await session.scalars(select(Incident).where(
            Incident.id.in_(set(provisional_ids) | canonical_ids),
        ))).all())
        work_orders = list((await session.scalars(select(WorkOrder).where(
            WorkOrder.incident_id.in_(set(provisional_ids) | canonical_ids),
        ))).all())
        queue = await OfficerService.get_officer_queue(session=session)
        visible_incident_cards = [item for item in queue if item.get("incident_id") in canonical_ids]
        incident = incidents[0]
        incident_sla = SLAService.calculate_incident_sla(incident)

    assert all(result["action_result"]["action_status"] in {"linked", "dispatched"} for result in results)
    assert len(active_links) == 3
    assert len(canonical_ids) == 1
    assert len(incidents) == 1
    assert len(work_orders) == 1
    assert results[0]["priority_result"]["priority"] == "high"
    assert results[2]["priority_result"]["priority"] == "critical"
    assert results[2]["priority_result"]["independent_report_boost_levels"] == 1
    assert incident.priority == "critical"
    assert work_orders[0].priority == "critical"
    assert incident_sla["priority"] == "critical"
    assert incident_sla["total_sla_hours"] == 12
    assert len(visible_incident_cards) == 1
    assert visible_incident_cards[0]["reporter_count"] == 3
    assert visible_incident_cards[0]["report_count"] == 3


@pytest.mark.asyncio
async def test_five_synthetic_reports_across_channels_preserve_reports_and_share_one_incident_work_order_and_notifications(monkeypatch):
    """Exercise all graph nodes with five reporters and deterministic simulated tools."""
    from app.mcp.client import mcp_client
    from app.services.agent_service import AgentService
    from app.schemas.agent import OfficerApprovalRequest

    calls: list[tuple[str, dict]] = []

    async def offline_tool(name, arguments):
        calls.append((name, dict(arguments)))
        if name == "civic_work_order_dispatch":
            return {"work_order_id": "WO-PHASE7-SYNTHETIC", "status": "DISPATCHED"}
        return {"delivery_id": f"SIM-{len(calls)}", "status": "DELIVERED"}

    monkeypatch.setattr(mcp_client, "call_tool", offline_tool)
    channels = (ComplaintSource.web, ComplaintSource.mobile, ComplaintSource.voice,
                ComplaintSource.whatsapp, ComplaintSource.mobile)
    descriptions = (
        "Garbage bags are piling beside the blue market shelter.",
        "Waste has overflowed from bins near the market bus stop.",
        "The trash collection point by the blue shelter is full.",
        "Refuse is scattered beside the market shelter after the bins filled.",
        "Overflowing rubbish containers near the same bus shelter.",
    )
    titles = ("Overflowing garbage at shelter", "Full waste bins by market", "Trash pile at bus stop",
              "Refuse scattered near shelter", "Rubbish bins overflowing")
    citizen_ids: list[str] = []
    complaint_ids: list[str] = []
    provisional_incident_ids: list[str] = []
    media_urls: list[str] = []
    results = []
    for index, (channel, title, description) in enumerate(zip(channels, titles, descriptions)):
        async with async_session_factory() as session:
            suffix = uuid.uuid4().hex
            citizen = User(
                email=f"phase7-citizen-{suffix}@test.invalid", hashed_password="unused",
                full_name=f"Synthetic reporter {index + 1}", phone=f"+1555{index + 1000000}",
            )
            session.add(citizen)
            await session.flush()
            complaint = Complaint(
                citizen_id=citizen.id, title=title, description=description,
                category=ComplaintCategory.garbage, status=ComplaintStatus.pending,
                priority=PriorityLevel.medium, latitude=11.1234, longitude=75.5432,
                address="Synthetic Verification Road", landmark="Synthetic blue shelter", source=channel,
            )
            session.add(complaint)
            await session.flush()
            photo_url = f"/uploads/phase7-synthetic-photo-{index + 1}.png"
            session.add(ComplaintMedia(
                complaint_id=complaint.id, media_type=MediaType.image, file_url=photo_url,
                file_name=f"synthetic-photo-{index + 1}.png", mime_type="image/png",
                perceptual_hash=f"000000000000000{index:x}",
            ))
            from app.services.incident_service import create_initial_incident_for_report

            incident, _link = await create_initial_incident_for_report(session, complaint)
            citizen_ids.append(citizen.id)
            complaint_ids.append(complaint.id)
            provisional_incident_ids.append(incident.id)
            media_urls.append(photo_url)
            await session.commit()
        async with async_session_factory() as session:
            result = await AgentService.orchestrate_complaint(complaint.id, session)
        if result.get("is_awaiting_approval"):
            async with async_session_factory() as session:
                result = await AgentService.submit_human_decision(
                    complaint_id=complaint.id,
                    approval_req=OfficerApprovalRequest(approved=True, officer_notes="Synthetic verification approval"),
                    officer_id=citizen_ids[0],
                    session=session,
                )
        results.append(result)

    async with async_session_factory() as session:
        preserved = list((await session.scalars(select(Complaint).where(Complaint.id.in_(complaint_ids)))).all())
        active_links = list((await session.scalars(select(ReportLink).where(
            ReportLink.complaint_id.in_(complaint_ids), ReportLink.is_active.is_(True),
        ))).all())
        incident_ids = {link.incident_id for link in active_links}
        scenario_incident_ids = set(provisional_incident_ids) | incident_ids
        scenario_incidents = list((await session.scalars(select(Incident).where(
            Incident.id.in_(scenario_incident_ids),
        ))).all())
        scenario_orders = list((await session.scalars(select(WorkOrder).where(
            WorkOrder.incident_id.in_(scenario_incident_ids),
        ))).all())
        deliveries = list((await session.scalars(select(NotificationDelivery).where(
            NotificationDelivery.incident_id.in_(scenario_incident_ids),
            NotificationDelivery.status == "delivered",
        ))).all())
        stored_media = list((await session.scalars(select(ComplaintMedia).where(
            ComplaintMedia.complaint_id.in_(complaint_ids),
        ))).all())
    notified_reporters = {row.recipient_user_id for row in deliveries}
    assert len(results) == 5
    summaries = [{
        "steps": result.get("steps_completed"),
        "awaiting": result.get("is_awaiting_approval"),
        "requires": result.get("requires_human_approval"),
        "dedup": result.get("deduplication_result", {}).get("decision"),
        "dedup_reason": result.get("deduplication_result", {}).get("reasons"),
        "dedup_scores": [
            (item.get("incident_id"), round(item.get("score", 0), 3), item.get("distance_m"))
            for item in result.get("deduplication_result", {}).get("ranked_candidates", [])
        ],
        "route": result.get("routing_result"),
        "approval_reason": result.get("approval_reason"),
        "action": result.get("action_result"),
    } for result in results]
    assert all(result.get("action_result", {}).get("action_status") in {"linked", "dispatched"} for result in results), [
        (item["dedup"], item["dedup_reason"], item["dedup_scores"], item["awaiting"], item["action"])
        for item in summaries
    ]
    assert len(scenario_incidents) == 1
    assert len(incident_ids) == 1
    assert len(scenario_orders) == 1
    assert len(preserved) == 5 and len(active_links) == 5
    assert {report.citizen_id for report in preserved} == set(citizen_ids)
    assert {report.source for report in preserved} == set(channels)
    assert {media.file_url for media in stored_media} == set(media_urls)
    assert notified_reporters == set(citizen_ids)
    assert sum(name == "civic_work_order_dispatch" for name, _ in calls) == 1
    print({
        "dataset_kind": "synthetic",
        "reports_preserved": len(preserved),
        "channels": len({report.source for report in preserved}),
        "incidents": len(scenario_incidents),
        "work_orders": len(scenario_orders),
        "reporters_notified": len(notified_reporters),
    })


def test_synthetic_nearby_different_potholes_do_not_auto_link():
    """A nearby hard negative should remain separate or go to review, never auto-link."""
    from datetime import datetime, timezone
    from app.deduplication.engine import CandidateIncident, MatchDecision, ReportEvidence, match_report

    report = ReportEvidence(
        report_id="synthetic-near-pothole", text="A road hole damages cars on North Road",
        category="pothole", latitude=12.0, longitude=77.0, address="North Road",
        photo_hashes=("ffffffffffffffff",), reported_at=datetime.now(timezone.utc),
    )
    candidate = CandidateIncident(
        incident_id="synthetic-other-pothole", title="A pothole damages cars on North Road",
        report_texts=("A pothole damages cars on North Road",), category="pothole", status="open",
        latitude=12.0, longitude=77.00027, address="North Road",
        photo_hashes=("0000000000000000",), created_at=report.reported_at,
    )
    assert match_report(report, [candidate]).decision != MatchDecision.auto_link


@pytest.mark.asyncio
async def test_citizens_can_read_only_their_report_while_officers_can_read_other_reports_and_tracker_is_public_safe():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        owner_id, owner_token = await _register(client, "owner")
        other_id, other_token = await _register(client, "other")
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        other_headers = {"Authorization": f"Bearer {other_token}"}
        created = await client.post("/api/complaints", headers=owner_headers, json={
            "title": "Private blocked drain", "description": "The drain beside my home is blocked.",
            "category": "drainage", "latitude": 12.98, "longitude": 77.60,
        })
        report_id = created.json()["id"]
        report_detail = await client.get(f"/api/complaints/{report_id}", headers=owner_headers)
        foreign_detail = await client.get(f"/api/complaints/{report_id}", headers=other_headers)
        own_list = await client.get("/api/complaints", headers=other_headers)
        async with async_session_factory() as session:
            link = await session.scalar(select(ReportLink).where(
                ReportLink.complaint_id == report_id, ReportLink.is_active.is_(True),
            ))
        tracker = await client.get(f"/api/incidents/{link.incident_id}/tracker")
        staff_login = await client.post("/api/auth/login", json={
            "email": "officer@demo.namma-civic.ai", "password": "password123",
        })
        staff_headers = {"Authorization": f"Bearer {staff_login.json()['access_token']}"}
        staff_detail = await client.get(f"/api/complaints/{report_id}", headers=staff_headers)
    assert report_detail.status_code == 200 and report_detail.json()["citizen_id"] == owner_id
    assert foreign_detail.status_code == 404
    assert own_list.status_code == 200 and all(row["citizen_id"] == other_id for row in own_list.json()["items"])
    assert staff_detail.status_code == 200
    assert tracker.status_code == 200
    assert not {"citizen_id", "reporter_id", "phone", "email", "description", "reporter_names"} & set(tracker.json())


@pytest.mark.asyncio
async def test_duplicate_webhook_delivery_with_same_idempotency_key_creates_one_report():
    from app.main import app
    from app.services.agent_service import AgentService

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _citizen_id, token = await _register(client, "webhook")
        headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": f"hook-{uuid.uuid4().hex}"}
        body = {
            "title": "Leaking water pipe at ward road",
            "description": "Water pipe leaks beside the ward road.",
            "category": "water_leakage", "latitude": 12.98, "longitude": 77.60,
            "source": "whatsapp",
        }
        first = await client.post("/api/complaints", json=body, headers=headers)
        replay = await client.post("/api/complaints", json=body, headers=headers)
        report_id = first.json()["id"]
        async with async_session_factory() as session:
            await AgentService.orchestrate_complaint(report_id, session)
        async with async_session_factory() as session:
            await AgentService.orchestrate_complaint(report_id, session)
            count = await session.scalar(select(func.count(Complaint.id)).where(Complaint.id == report_id))
    assert first.status_code == 201 and replay.status_code == 201
    assert replay.json()["id"] == report_id
    assert count == 1


@pytest.mark.asyncio
async def test_malformed_image_upload_is_rejected_after_mime_check():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _user_id, token = await _register(client, "media")
        response = await client.post(
            "/api/complaints/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("broken.png", BytesIO(b"not a real png image"), "image/png")},
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_ai_provider_failure_falls_back_safely_and_requires_officer_review(monkeypatch):
    import importlib
    from app.agents.nodes import routing_node
    from app.agents.nodes.intake_node import intake_node

    intake_module = importlib.import_module("app.agents.nodes.intake_node")

    class BrokenProvider:
        async def synthesize_multimodal_triage(self, **_kwargs):
            raise RuntimeError("synthetic provider outage")

    monkeypatch.setattr(intake_module, "get_ai_provider", lambda: BrokenProvider())
    intake = await intake_node({
        "complaint_id": "synthetic-ai-outage", "title": "Blocked drain",
        "description": "The drain is blocked on Ward Road.", "category": "drainage",
        "steps_completed": [], "errors": [],
    })
    assert intake["intake_result"]["provider_failed"] is True
    route = await routing_node({
        "complaint_id": "synthetic-ai-outage", "title": "Blocked drain",
        "description": "The drain is blocked on Ward Road.", "category": "drainage",
        "intake_result": intake["intake_result"],
        "validation_result": {"is_valid": True},
        "deduplication_result": {"decision": "new_incident", "is_duplicate": False},
        "steps_completed": intake["steps_completed"],
    })
    assert route["requires_human_approval"] is True
    assert "provider" in route["approval_reason"].lower()


@pytest.mark.asyncio
async def test_agent_state_for_another_citizens_report_is_not_disclosed():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _owner_id, owner_token = await _register(client, "state-owner")
        _other_id, other_token = await _register(client, "state-other")
        created = await client.post("/api/complaints", headers={"Authorization": f"Bearer {owner_token}"}, json={
            "title": "Private light outage", "description": "The lamp is out at my house.",
            "category": "street_light",
        })
        response = await client.get(
            f"/api/agents/state/{created.json()['id']}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
    assert response.status_code == 404
