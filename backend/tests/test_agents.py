"""
Namma Civic — LangGraph Multi-Agent System Tests (Phase 5)
Tests specialized agent nodes, state graph compilation, conditional branching, checkpointer persistence, and Human-in-the-Loop approval.
"""
from __future__ import annotations

import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.graph import build_civic_action_graph, civic_action_graph
from app.agents.nodes import (
    action_node,
    approval_node,
    deduplication_node,
    intake_node,
    routing_node,
    validation_node,
)
from app.agents.state import CivicActionState
from app.main import app
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.complaint import Complaint, ComplaintCategory, ComplaintStatus, PriorityLevel
from app.models.user import User
from app.services.incident_service import create_initial_incident_for_report

BASE = "http://test"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def citizen_payload():
    uid = uuid.uuid4().hex[:8]
    return {
        "email": f"agent_cit_{uid}@namma-civic.org",
        "password": "testpass1",
        "full_name": "Agent Citizen",
        "phone": "+919876543201",
    }


@pytest.fixture
def officer_login_payload():
    return {
        "email": "officer@demo.namma-civic.ai",
        "password": "password123",
    }


async def get_token(client: AsyncClient, payload: dict, is_register: bool = True) -> str:
    if is_register:
        reg = await client.post("/api/auth/register", json=payload)
        assert reg.status_code == 201
        return reg.json()["access_token"]
    else:
        log = await client.post("/api/auth/login", json=payload)
        assert log.status_code == 200
        return log.json()["access_token"]


async def _persist_graph_report(complaint_id: str, title: str, description: str, category: str, lat: float, lon: float):
    """Give graph integration tests a valid persisted report and initial incident."""
    async with async_session_factory() as session:
        citizen = await session.scalar(select(User).where(User.email == "citizen@demo.namma-civic.ai"))
        assert citizen is not None
        report = Complaint(
            id=complaint_id,
            citizen_id=citizen.id,
            title=title,
            description=description,
            category=ComplaintCategory(category),
            status=ComplaintStatus.pending,
            priority=PriorityLevel.medium,
            latitude=lat,
            longitude=lon,
        )
        session.add(report)
        await session.flush()
        await create_initial_incident_for_report(session, report)
        await session.commit()


# ── Unit Tests: Specialized Nodes ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_intake_node_processing():
    state: CivicActionState = {
        "complaint_id": "test-c1",
        "title": "Severe pothole on main road",
        "description": "Large road crater damaging car suspensions",
        "category": "pothole",
        "steps_completed": [],
    }
    result = await intake_node(state)
    assert "intake_result" in result
    assert result["intake_result"]["detected_category"] in ["pothole", "ROADS"]
    assert "intake" in result["steps_completed"]


@pytest.mark.asyncio
async def test_validation_node_legitimate_civic():
    state: CivicActionState = {
        "complaint_id": "test-c2",
        "title": "Broken street lamp causing darkness",
        "description": "The lamp post fell over on the sidewalk near 5th Cross",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "steps_completed": ["intake"],
    }
    result = await validation_node(state)
    assert result["validation_result"]["is_valid"] is True
    assert result["validation_result"]["is_actionable"] is True
    assert "validation" in result["steps_completed"]


@pytest.mark.asyncio
async def test_validation_node_spam_gibberish():
    state: CivicActionState = {
        "complaint_id": "test-c3",
        "title": "asdf",
        "description": "asdfghjkl xxxxxxxx crypto loan",
        "steps_completed": ["intake"],
    }
    result = await validation_node(state)
    assert result["validation_result"]["is_valid"] is False
    assert result["validation_result"]["spam_score"] > 0.4
    assert result["current_step"] == "approval"


@pytest.mark.asyncio
async def test_routing_node_policy_and_sla():
    state: CivicActionState = {
        "complaint_id": "test-c4",
        "category": "water_leakage",
        "intake_result": {
            "detected_category": "water_leakage",
            "severity": 9,
            "urgency_score": 0.9,
            "confidence_score": 0.95,
        },
        "validation_result": {"is_valid": True},
        "deduplication_result": {"is_duplicate": False},
        "steps_completed": ["intake", "validation", "deduplication"],
    }
    result = await routing_node(state)
    assert result["routing_result"]["department_code"] == "WATER"
    assert result["routing_result"]["priority"] == "critical"
    assert result["routing_result"]["sla_hours"] == 12
    # Severity 9 triggers Human-in-the-loop
    assert result["requires_human_approval"] is True
    assert result["is_awaiting_approval"] is True


@pytest.mark.asyncio
async def test_approval_node_awaiting_and_resumption():
    # 1. Without decision -> pauses
    state_awaiting: CivicActionState = {
        "complaint_id": "test-c5",
        "requires_human_approval": True,
        "human_decision": None,
        "steps_completed": ["intake", "validation", "deduplication", "routing"],
    }
    res_pause = await approval_node(state_awaiting)
    assert res_pause["is_awaiting_approval"] is True

    # 2. With officer approval and department override
    state_approved: CivicActionState = {
        "complaint_id": "test-c5",
        "requires_human_approval": True,
        "routing_result": {"department_code": "PUBLIC_WORKS", "priority": "medium"},
        "human_decision": {
            "approved": True,
            "officer_notes": "Reassigned to Drainage squad",
            "override_dept": "DRAINAGE",
            "override_priority": "high",
        },
        "steps_completed": ["intake", "validation", "deduplication", "routing"],
    }
    res_app = await approval_node(state_approved)
    assert res_app["is_awaiting_approval"] is False
    assert res_app["routing_result"]["department_code"] == "DRAINAGE"
    assert res_app["routing_result"]["priority"] == "high"
    assert res_app["current_step"] == "action"


# ── Graph Execution Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_graph_autonomous_flow():
    """Test standard report that passes without HITL interruption."""
    saver = MemorySaver()
    graph = build_civic_action_graph(checkpointer=saver)

    cid = str(uuid.uuid4())
    config = {"configurable": {"thread_id": cid}}

    initial_state: CivicActionState = {
        "complaint_id": cid,
        "title": "Minor trash accumulation near bus stop",
        "description": "Several paper cups and plastic wrappers on the sidewalk.",
        "category": "garbage",
        "latitude": 22.5726,
        "longitude": 88.3639,
        "media_urls": [],
        "steps_completed": [],
        "errors": [],
    }

    await _persist_graph_report(cid, initial_state["title"], initial_state["description"], "garbage", 40.0, -70.0)

    final_state = await graph.ainvoke(initial_state, config=config)
    assert "intake" in final_state["steps_completed"]
    assert "vision" in final_state["steps_completed"]
    assert "validation" in final_state["steps_completed"]
    assert "deduplication" in final_state["steps_completed"]
    assert "priority" in final_state["steps_completed"]
    assert "routing" in final_state["steps_completed"]
    assert "action" in final_state["steps_completed"]
    assert "monitoring" in final_state["steps_completed"]
    assert "resolution_verification" in final_state["steps_completed"]
    assert final_state["action_result"]["action_status"] == "dispatched"


@pytest.mark.asyncio
async def test_graph_hitl_pause_and_resume():
    """Test high-severity complaint pausing at approval gate and resuming after officer sign-off."""
    saver = MemorySaver()
    graph = build_civic_action_graph(checkpointer=saver)

    cid = str(uuid.uuid4())
    config = {"configurable": {"thread_id": cid}}

    initial_state: CivicActionState = {
        "complaint_id": cid,
        "title": "Critical gas or sewer pipeline blowout with sinkhole",
        "description": "Extremely dangerous massive emergency on arterial highway.",
        "category": "drainage",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "media_urls": [],
        "steps_completed": [],
        "errors": [],
    }

    await _persist_graph_report(cid, initial_state["title"], initial_state["description"], "drainage", 50.0, -100.0)

    # Step 1: Run graph until pause
    paused_state = await graph.ainvoke(initial_state, config=config)
    assert paused_state["requires_human_approval"] is True
    assert paused_state["is_awaiting_approval"] is True
    assert "action" not in paused_state["steps_completed"]

    # Step 2: Officer provides approval
    resume_payload = {
        "human_decision": {
            "approved": True,
            "officer_notes": "Emergency repair crew confirmed and dispatched.",
            "override_priority": "critical",
        },
        "is_awaiting_approval": False,
    }
    resumed_state = await graph.ainvoke(resume_payload, config=config)
    assert "action" in resumed_state["steps_completed"]
    assert resumed_state["action_result"]["action_status"] == "dispatched"


# ── API Endpoints Tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_agents_orchestrate_and_state(citizen_payload, officer_login_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        cit_token = await get_token(client, citizen_payload)
        headers = {"Authorization": f"Bearer {cit_token}"}

        # 1. Create a complaint
        created = await client.post(
            "/api/complaints",
            json={
                "title": "Open electrical wiring near playground",
                "description": "Exposed high-voltage wires hanging dangerously low.",
                "category": "street_light",
                "latitude": 13.0827,
                "longitude": 80.2707,
            },
            headers=headers,
        )
        assert created.status_code == 201
        cid = created.json()["id"]

        # 2. Orchestrate via /api/agents/orchestrate/{id}
        orch_resp = await client.post(f"/api/agents/orchestrate/{cid}", headers=headers)
        assert orch_resp.status_code == 200
        orch_data = orch_resp.json()
        assert orch_data["complaint_id"] == cid
        assert "intake" in orch_data["steps_completed"]
        assert "validation" in orch_data["steps_completed"]

        # 3. Check state via /api/agents/state/{id}
        state_resp = await client.get(f"/api/agents/state/{cid}", headers=headers)
        assert state_resp.status_code == 200
        state_data = state_resp.json()
        assert state_data["complaint_id"] == cid


@pytest.mark.asyncio
async def test_api_agents_officer_approval(citizen_payload, officer_login_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        cit_token = await get_token(client, citizen_payload)
        officer_token = await get_token(client, officer_login_payload, is_register=False)

        # 1. Create complaint as citizen
        created = await client.post(
            "/api/complaints",
            json={
                "title": "Flooding from damaged culvert",
                "description": "Drainage canal overflow flooding residential street.",
                "category": "drainage",
                "latitude": 19.0760,
                "longitude": 72.8777,
            },
            headers={"Authorization": f"Bearer {cit_token}"},
        )
        assert created.status_code == 201
        cid = created.json()["id"]

        # 2. Trigger orchestration
        await client.post(f"/api/agents/orchestrate/{cid}", headers={"Authorization": f"Bearer {cit_token}"})

        # 3. Officer submits approval via /api/agents/approve/{id}
        app_resp = await client.post(
            f"/api/agents/approve/{cid}",
            json={
                "approved": True,
                "officer_notes": "Approved by Municipal Engineer. Dispatched to drainage crew.",
                "override_dept": "DRAINAGE",
                "override_priority": "high",
            },
            headers={"Authorization": f"Bearer {officer_token}"},
        )
        assert app_resp.status_code == 200
        app_data = app_resp.json()
        assert app_data["human_decision"]["approved"] is True
        assert app_data["routing_result"]["department_code"] == "DRAINAGE"
        assert app_data["action_result"]["action_status"] == "dispatched"
