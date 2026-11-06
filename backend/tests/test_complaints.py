"""
Namma Civic — Complaints Endpoint Tests (Phase 3)
"""
from __future__ import annotations

import io
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def citizen_payload():
    uid = uuid.uuid4().hex[:8]
    return {
        "email": f"complaint_user_{uid}@namma-civic.org",
        "password": "testpass1",
        "full_name": "Complaint Tester",
        "phone": "+919876543210",
    }


async def get_auth_token(client: AsyncClient, payload: dict) -> str:
    reg = await client.post("/api/auth/register", json=payload)
    assert reg.status_code == 201
    return reg.json()["access_token"]


# ── Submission Tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_complaint_authenticated(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        token = await get_auth_token(client, citizen_payload)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/complaints",
            json={
                "title": "Hazardous pothole on 5th Avenue",
                "description": "Deep pothole causing vehicle damage near the intersection.",
                "category": "pothole",
                "latitude": 22.5726,
                "longitude": 88.3639,
                "address": "5th Avenue, Sector 1",
                "landmark": "Near Central Bank",
            },
            headers=headers,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Hazardous pothole on 5th Avenue"
    assert data["category"] == "pothole"
    assert data["status"] == "pending"
    assert data["priority"] == "medium"
    assert data["latitude"] == 22.5726
    assert data["longitude"] == 88.3639
    assert len(data["timeline"]) == 1
    assert data["timeline"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_create_complaint_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        resp = await client.post(
            "/api/complaints",
            json={
                "title": "Unauthenticated report",
                "description": "This should fail because no token was supplied.",
                "category": "garbage",
            },
        )
    assert resp.status_code == 401


# ── File Upload Tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_media_image(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        token = await get_auth_token(client, citizen_payload)
        headers = {"Authorization": f"Bearer {token}"}

        # A real in-memory PNG: MIME validation is paired with content validation.
        from PIL import Image
        image_buffer = io.BytesIO()
        Image.new("RGB", (1, 1), color="red").save(image_buffer, format="PNG")
        image_buffer.seek(0)
        files = {"file": ("pothole.png", image_buffer, "image/png")}

        resp = await client.post("/api/complaints/upload", files=files, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["file_url"].startswith("/uploads/")
    assert data["media_type"] == "image"
    assert data["mime_type"] == "image/png"


@pytest.mark.asyncio
async def test_create_complaint_with_media(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        token = await get_auth_token(client, citizen_payload)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/complaints",
            json={
                "title": "Overflowing garbage bin",
                "description": "Waste bins have not been emptied for three days.",
                "category": "garbage",
                "media": [
                    {
                        "file_url": "/uploads/mock_garbage.jpg",
                        "file_name": "garbage.jpg",
                        "file_size": 2048,
                        "mime_type": "image/jpeg",
                        "media_type": "image",
                        "caption": "Photo of overflowing bin",
                    }
                ],
            },
            headers=headers,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert len(data["media"]) == 1
    assert data["media"][0]["file_name"] == "garbage.jpg"


# ── Listing & Detail Tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_my_complaints_and_summary(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        token = await get_auth_token(client, citizen_payload)
        headers = {"Authorization": f"Bearer {token}"}

        # Create two complaints
        await client.post(
            "/api/complaints",
            json={
                "title": "Broken street light #1",
                "description": "Streetlight pole #42 is dark at night.",
                "category": "street_light",
            },
            headers=headers,
        )
        await client.post(
            "/api/complaints",
            json={
                "title": "Water leak on main street",
                "description": "Water pipe leaking clean water onto the road.",
                "category": "water_leakage",
            },
            headers=headers,
        )

        # Get my complaints
        list_resp = await client.get("/api/complaints/my", headers=headers)
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["total"] >= 2

        # Get summary
        sum_resp = await client.get("/api/complaints/my/summary", headers=headers)
        assert sum_resp.status_code == 200
        summary = sum_resp.json()
        assert summary["total"] >= 2
        assert summary["active"] >= 2


@pytest.mark.asyncio
async def test_get_complaint_by_id(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        token = await get_auth_token(client, citizen_payload)
        headers = {"Authorization": f"Bearer {token}"}

        created = await client.post(
            "/api/complaints",
            json={
                "title": "Clogged storm drain",
                "description": "Drain overflowing with rain water.",
                "category": "drainage",
            },
            headers=headers,
        )
        complaint_id = created.json()["id"]

        detail = await client.get(f"/api/complaints/{complaint_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["id"] == complaint_id


@pytest.mark.asyncio
async def test_get_complaint_not_found(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        token = await get_auth_token(client, citizen_payload)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/api/complaints/nonexistent-uuid-1234", headers=headers)
    assert resp.status_code == 404


# ── Update Tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_complaint_by_citizen(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        token = await get_auth_token(client, citizen_payload)
        headers = {"Authorization": f"Bearer {token}"}

        created = await client.post(
            "/api/complaints",
            json={
                "title": "Initial Title",
                "description": "Initial description text here.",
                "category": "other",
            },
            headers=headers,
        )
        complaint_id = created.json()["id"]

        update_resp = await client.patch(
            f"/api/complaints/{complaint_id}",
            json={"title": "Updated Title After Clarification"},
            headers=headers,
        )
        assert update_resp.status_code == 403
        detail = await client.get(f"/api/complaints/{complaint_id}", headers=headers)
        assert detail.json()["title"] == "Initial Title"


@pytest.mark.asyncio
async def test_officer_update_status(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        # Create complaint as citizen
        cit_token = await get_auth_token(client, citizen_payload)
        created = await client.post(
            "/api/complaints",
            json={
                "title": "Pothole to be inspected",
                "description": "Major pothole needing urgent repair.",
                "category": "pothole",
            },
            headers={"Authorization": f"Bearer {cit_token}"},
        )
        complaint_id = created.json()["id"]

        # Login as demo officer
        officer_login = await client.post(
            "/api/auth/login",
            json={"email": "officer@demo.namma-civic.ai", "password": "password123"},
        )
        assert officer_login.status_code == 200
        off_token = officer_login.json()["access_token"]

        # Officer updates status to in_progress
        patch_resp = await client.patch(
            f"/api/complaints/{complaint_id}",
            json={
                "status": "in_progress",
                "priority": "high",
                "note": "Road repair crew dispatched to location.",
            },
            headers={"Authorization": f"Bearer {off_token}"},
        )
        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data["status"] == "in_progress"
        assert data["priority"] == "high"
        # Timeline should now have 2 entries (pending -> in_progress)
        assert len(data["timeline"]) == 2
        assert data["timeline"][1]["status"] == "in_progress"
