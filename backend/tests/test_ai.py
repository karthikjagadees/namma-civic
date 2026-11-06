"""
Namma Civic — AI Intake & Multimodal Understanding Tests (Phase 4)
Tests Mock Provider heuristics, standalone triage endpoints, and automated complaint enrichment.
"""
from __future__ import annotations

import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.ai.factory import create_ai_provider, get_ai_provider
from app.core.ai.gemini_provider import GeminiProvider
from app.core.ai.mock_provider import MockAIProvider
from app.core.ai.openai_provider import OpenAIProvider
from app.main import app

BASE = "http://test"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def citizen_payload():
    uid = uuid.uuid4().hex[:8]
    return {
        "email": f"ai_tester_{uid}@namma-civic.org",
        "password": "testpass1",
        "full_name": "AI Intake Tester",
        "phone": "+919876543299",
    }


async def get_auth_token(client: AsyncClient, payload: dict) -> str:
    reg = await client.post("/api/auth/register", json=payload)
    assert reg.status_code == 201
    return reg.json()["access_token"]


# ── Unit Tests: AI Provider Layer ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mock_provider_text_analysis_pothole():
    provider = MockAIProvider()
    res = await provider.analyze_text("Massive dangerous pothole causing accidents near Metro Station")
    assert res.detected_category == "pothole"
    assert res.severity >= 6
    assert res.confidence_score >= 0.8
    assert res.recommended_department in ["Roads & Infrastructure", "ROADS"]
    assert "pothole" in res.reasoning.lower() or "road" in res.reasoning.lower()


@pytest.mark.asyncio
async def test_mock_provider_text_analysis_water_leak():
    provider = MockAIProvider()
    res = await provider.analyze_text("Main water pipeline burst with severe flooding on 3rd Cross")
    assert res.detected_category == "water_leakage"
    assert res.severity >= 6
    assert "Water" in res.recommended_department or "WATER" in res.recommended_department


@pytest.mark.asyncio
async def test_mock_provider_vision_analysis():
    provider = MockAIProvider()
    res = await provider.analyze_image("http://localhost:8000/uploads/pothole_crater.jpg")
    assert res.has_damage_detected is True
    assert res.visual_severity_estimate >= 5
    assert len(res.visual_features) > 0
    assert res.safety_hazard_level in ["low", "medium", "high", "critical"]


@pytest.mark.asyncio
async def test_ai_provider_factory_instantiation():
    mock_prov = create_ai_provider("mock")
    assert isinstance(mock_prov, MockAIProvider)

    openai_prov = create_ai_provider("openai")
    assert isinstance(openai_prov, OpenAIProvider)

    gemini_prov = create_ai_provider("gemini")
    assert isinstance(gemini_prov, GeminiProvider)


# ── API Tests: Standalone AI Endpoint ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_ai_analyze_standalone():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        resp = await client.post(
            "/api/ai/analyze",
            json={
                "text": "Huge garbage overflow spreading foul smell and flies near market",
                "category_hint": "garbage",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["detected_category"] in ["garbage", "SANITATION"]
    assert data["confidence_score"] >= 0.7
    assert data["severity"] >= 4
    assert "Sanitation" in data["recommended_department"] or "SANITATION" in data["recommended_department"]
    assert data["provider_used"] in ["mock", "openai", "gemini", "groq"]


@pytest.mark.asyncio
async def test_api_ai_analyze_validation_error():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        resp = await client.post(
            "/api/ai/analyze",
            json={"text": "no"},  # Less than min_length 3
        )
    assert resp.status_code == 422


# ── Integration Tests: Autonomous Complaint Intake & Triage ──────────────────

@pytest.mark.asyncio
async def test_complaint_creation_triggers_auto_ai_triage(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        token = await get_auth_token(client, citizen_payload)
        headers = {"Authorization": f"Bearer {token}"}

        # Create a complaint
        resp = await client.post(
            "/api/complaints",
            json={
                "title": "Severe dark street with broken light pole",
                "description": "The entire residential lane is pitch dark due to a knocked down light pole.",
                "category": "other",
                "latitude": 12.9716,
                "longitude": 77.5946,
                "address": "10th Cross, Indiranagar",
                "landmark": "Near Children Park",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        complaint_data = resp.json()
        complaint_id = complaint_data["id"]

        # Trigger AI triage endpoint for this complaint
        ai_trigger = await client.post(f"/api/complaints/{complaint_id}/analyze", headers=headers)
        assert ai_trigger.status_code == 200

        # Fetch detail by ID
        detail_resp = await client.get(f"/api/complaints/{complaint_id}", headers=headers)
        assert detail_resp.status_code == 200
        detail = detail_resp.json()

        # AI analysis should be attached and populated
        assert detail["ai_analysis"] is not None
        ai = detail["ai_analysis"]
        assert ai["complaint_id"] == complaint_id
        assert ai["detected_category"] in ["street_light", "STREETLIGHTS", "ELECTRICAL", "ROADS"]
        assert ai["confidence_score"] >= 0.6
        assert ai["severity"] >= 1
        assert len(ai["reasoning"]) > 10

        # Status should have progressed to verified
        assert detail["status"] == "verified"

        # Timeline should include an AI audit note
        timeline_notes = [entry["note"] for entry in detail["timeline"] if entry["note"]]
        assert any("AI" in note for note in timeline_notes)


@pytest.mark.asyncio
async def test_get_and_reanalyze_complaint_ai(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        token = await get_auth_token(client, citizen_payload)
        headers = {"Authorization": f"Bearer {token}"}

        # Create complaint
        resp = await client.post(
            "/api/complaints",
            json={
                "title": "Sewage overflow on main road",
                "description": "Drainage manhole overflowing onto street causing contamination.",
                "category": "drainage",
                "latitude": 28.6139,
                "longitude": 77.2090,
            },
            headers=headers,
        )
        assert resp.status_code == 201
        cid = resp.json()["id"]

        # 1. Trigger AI analysis via /api/ai/reanalyze/{id}
        re_resp = await client.post(f"/api/ai/reanalyze/{cid}", headers=headers)
        assert re_resp.status_code == 200
        re_data = re_resp.json()
        assert re_data["complaint_id"] == cid
        assert re_data["confidence_score"] >= 0.5
        assert re_data["detected_category"] in ["drainage", "DRAINAGE", "WATER_SUPPLY", "SANITATION"]

        # 2. Fetch AI analysis directly from /api/ai/analysis/{id}
        ai_resp = await client.get(f"/api/ai/analysis/{cid}", headers=headers)
        assert ai_resp.status_code == 200
        ai_data = ai_resp.json()
        assert ai_data["complaint_id"] == cid
        assert ai_data["detected_category"] in ["drainage", "DRAINAGE", "WATER_SUPPLY", "SANITATION"]


@pytest.mark.asyncio
async def test_get_ai_analysis_nonexistent(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        token = await get_auth_token(client, citizen_payload)
        resp = await client.get(
            "/api/ai/analysis/nonexistent-id-0000",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
