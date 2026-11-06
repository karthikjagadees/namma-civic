"""Phase 4 tests for the added lifecycle agents."""
from __future__ import annotations

import asyncio
import importlib
import uuid

import pytest

from app.agents.graph import build_civic_action_graph
from app.agents.nodes import action_node, monitoring_node, priority_node, resolution_verification_node, vision_node
from app.agents.state import CivicActionState
from app.core.database import async_session_factory
from app.models.complaint import Complaint, ComplaintCategory, ComplaintStatus, PriorityLevel
from app.models.incident import Incident, IncidentStatus
from app.models.report_link import ReportLink
from app.models.user import User
from app.models.work_order import WorkOrder
from sqlalchemy import func, select


@pytest.mark.asyncio
async def test_vision_node_reuses_offline_intake_analysis():
    state: CivicActionState = {
        "intake_result": {"vision_analysis": {"damage_type": "pothole"}},
        "steps_completed": ["intake"],
    }

    result = await vision_node(state)

    assert result["vision_result"]["analysis"]["damage_type"] == "pothole"
    assert "vision" in result["steps_completed"]


@pytest.mark.asyncio
async def test_priority_node_escalates_for_independent_report_count():
    state: CivicActionState = {
        "routing_result": {"priority": "medium", "severity": 3},
        "incident_report_count": 3,
        "steps_completed": ["deduplication"],
    }

    result = await priority_node(state)

    assert result["priority_result"]["report_count"] == 3
    assert result["priority_result"]["priority"] == "high"
    assert result["routing_result"]["priority"] == "high"
    assert result["priority_result"]["independent_report_boost_levels"] == 1


@pytest.mark.asyncio
async def test_monitoring_node_reports_scheduled_worker_delegation(monkeypatch):
    module = importlib.import_module("app.agents.nodes.monitoring_node")

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def scalar(self, _query):
            return object()

    monkeypatch.setattr(module, "async_session_factory", lambda: Session())
    monkeypatch.setattr(module.SLAService, "calculate_sla", lambda _complaint: {"sla_status": "ON_TRACK"})
    state: CivicActionState = {"complaint_id": "report-1", "steps_completed": ["action"]}

    result = await monitoring_node(state)

    assert result["monitoring_result"]["status"] == "ON_TRACK"
    assert result["monitoring_result"]["delegated_to"] == "scheduled_sla_worker"
    assert "monitoring" in result["steps_completed"]


@pytest.mark.asyncio
async def test_resolution_verification_node_skips_without_resolution_evidence():
    result = await resolution_verification_node({"complaint_id": "report-1", "steps_completed": []})
    assert result["verification_result"]["status"] == "not_requested"


@pytest.mark.asyncio
async def test_resolution_verification_node_delegates_submitted_evidence(monkeypatch):
    module = importlib.import_module("app.agents.nodes.resolution_verification_node")
    expected = {"new_status": "resolved"}

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    async def verify(**kwargs):
        assert kwargs["complaint_id"] == "report-1"
        assert kwargs["resolution_notes"] == "patched"
        return expected

    monkeypatch.setattr(module, "async_session_factory", lambda: Session())
    monkeypatch.setattr(module.ResolutionVerificationService, "verify_resolution_evidence", verify)
    result = await resolution_verification_node({
        "complaint_id": "report-1", "resolution_notes": "patched", "steps_completed": []
    })

    assert result["verification_result"] == expected


def test_graph_registers_the_phase_four_lifecycle_nodes():
    graph = build_civic_action_graph()
    nodes = set(graph.get_graph().nodes)

    assert {"vision", "priority", "monitoring", "resolution_verification"} <= nodes


@pytest.mark.asyncio
async def test_action_links_duplicate_and_reuses_incident_work_order(monkeypatch):
    from app.mcp.client import mcp_client

    calls = []

    async def mock_tool(name, arguments):
        calls.append((name, arguments))
        if name == "civic_work_order_dispatch":
            return {"work_order_id": "WO-STABLE-1", "status": "DISPATCHED"}
        return {"delivery_id": "SMS-1", "status": "DELIVERED"}

    monkeypatch.setattr(mcp_client, "call_tool", mock_tool)
    async with async_session_factory() as session:
        citizen = User(
            email=f"phase4-{uuid.uuid4().hex}@example.test",
            hashed_password="unused",
            full_name="Phase Four Citizen",
            phone="+919900001234",
        )
        second_citizen = User(
            email=f"phase4-{uuid.uuid4().hex}@example.test",
            hashed_password="unused",
            full_name="Second Phase Four Citizen",
            phone="+919900005678",
        )
        session.add_all([citizen, second_citizen])
        await session.flush()
        first = Complaint(
            citizen_id=second_citizen.id, title="Pothole near park", description="Deep pothole",
            category=ComplaintCategory.pothole, status=ComplaintStatus.pending,
            priority=PriorityLevel.medium, latitude=12.0, longitude=77.0,
        )
        second = Complaint(
            citizen_id=citizen.id, title="Pothole near park", description="Deep pothole",
            category=ComplaintCategory.pothole, status=ComplaintStatus.pending,
            priority=PriorityLevel.medium, latitude=12.0, longitude=77.0,
        )
        session.add_all([first, second])
        await session.flush()
        first_incident = Incident(
            title=first.title, category=first.category, status=IncidentStatus.open,
            latitude=first.latitude, longitude=first.longitude,
        )
        second_incident = Incident(
            title=second.title, category=second.category, status=IncidentStatus.open,
            latitude=second.latitude, longitude=second.longitude,
        )
        session.add_all([first_incident, second_incident])
        await session.flush()
        session.add_all([
            ReportLink(complaint_id=first.id, incident_id=first_incident.id, decision_source="auto"),
            ReportLink(complaint_id=second.id, incident_id=second_incident.id, decision_source="auto"),
        ])
        await session.commit()
        first_id, second_id = first.id, second.id
        incident_ids = {first_incident.id, second_incident.id}

    base_state = {
        "routing_result": {"department_code": "ROADS", "department_name": "Roads", "priority": "medium", "sla_hours": 48},
        "steps_completed": [],
    }
    first_state = {
        **base_state,
        "complaint_id": first_id,
        "deduplication_result": {"decision": "new_incident"},
    }
    second_state = {
        **base_state,
        "complaint_id": second_id,
        "deduplication_result": {"decision": "new_incident"},
    }
    first_result, result = await asyncio.gather(action_node(first_state), action_node(second_state))
    retry_result = await action_node(second_state)

    assert result["action_result"]["match_decision"] == "auto_link", result["action_result"]["match_decision"]
    assert first_result["action_result"]["action_status"] in {"linked", "dispatched"}
    assert retry_result["action_result"]["match_decision"] == "auto_link"
    assert result["action_result"]["work_order_id"] == "WO-STABLE-1"
    dispatch_calls = [args for name, args in calls if name == "civic_work_order_dispatch"]
    assert len(dispatch_calls) == 1
    sms_calls = [args for name, args in calls if name == "notify_citizen_sms"]
    assert sms_calls and all(call["phone_number"] in {"+919900001234", "+919900005678"} for call in sms_calls)
    async with async_session_factory() as session:
        active_link = await session.scalar(select(ReportLink).where(
            ReportLink.complaint_id == second_id, ReportLink.is_active.is_(True)
        ))
        first_link = await session.scalar(select(ReportLink).where(
            ReportLink.complaint_id == first_id, ReportLink.is_active.is_(True)
        ))
        assert active_link.incident_id == first_link.incident_id
        assert active_link.incident_id in incident_ids
        assert await session.scalar(select(func.count(WorkOrder.id)).where(
            WorkOrder.incident_id.in_(incident_ids)
        )) == 1


@pytest.mark.asyncio
async def test_action_reports_database_failure_without_claiming_dispatch(monkeypatch):
    import importlib

    module = importlib.import_module("app.agents.nodes.action_node")

    class BrokenSession:
        async def __aenter__(self):
            raise RuntimeError("synthetic database outage")

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr(module, "async_session_factory", lambda: BrokenSession())
    result = await action_node({"complaint_id": "missing", "steps_completed": []})

    assert result["action_result"]["action_status"] == "failed"
    assert result["action_result"]["notifications_queued"] is False
    assert result["action_result"]["work_order_id"] is None


@pytest.mark.asyncio
async def test_mock_civic_dispatch_is_stable_for_a_retry_key():
    from app.mcp.servers.civic_mcp import execute_civic_tool

    arguments = {
        "complaint_id": "report-1", "department_code": "ROADS",
        "priority": "high", "idempotency_key": "incident-order-key-1",
    }
    first = await execute_civic_tool("civic_work_order_dispatch", arguments)
    retry = await execute_civic_tool("civic_work_order_dispatch", arguments)

    assert first["work_order_id"] == retry["work_order_id"]
