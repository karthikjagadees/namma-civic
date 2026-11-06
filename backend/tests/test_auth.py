"""
Namma Civic — Auth endpoint tests (Phase 2)
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


# ── Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def citizen_payload():
    uid = uuid.uuid4().hex[:8]
    return {
        "email": f"citizen_{uid}@namma-civic.org",
        "password": "testpass1",
        "full_name": "Test Citizen",
        "phone": "+919876543210",
    }


@pytest.fixture
def officer_payload():
    uid = uuid.uuid4().hex[:8]
    return {
        "email": f"officer_{uid}@namma-civic.org",
        "password": "officerpass1",
        "full_name": "Test Officer",
    }


# ── Registration ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_citizen_success(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        resp = await client.post("/api/auth/register", json=citizen_payload)

    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == citizen_payload["email"]
    assert data["user"]["role"] == "citizen"
    assert data["user"]["is_active"] is True


@pytest.mark.asyncio
async def test_register_duplicate_email(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        await client.post("/api/auth/register", json=citizen_payload)
        resp = await client.post("/api/auth/register", json=citizen_payload)

    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_weak_password():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        resp = await client.post("/api/auth/register", json={
            "email": "weak@namma-civic.org",
            "password": "short",
            "full_name": "Weak User",
        })
    assert resp.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_register_invalid_email():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        resp = await client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "validpass1",
            "full_name": "Bad Email",
        })
    assert resp.status_code == 422


# ── Login ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        await client.post("/api/auth/register", json=citizen_payload)
        resp = await client.post("/api/auth/login", json={
            "email": citizen_payload["email"],
            "password": citizen_payload["password"],
        })

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == citizen_payload["email"]


@pytest.mark.asyncio
async def test_login_wrong_password(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        await client.post("/api/auth/register", json=citizen_payload)
        resp = await client.post("/api/auth/login", json={
            "email": citizen_payload["email"],
            "password": "WRONGPASSWORD1",
        })

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        resp = await client.post("/api/auth/login", json={
            "email": "nobody@nowhere.com",
            "password": "somepass1",
        })
    assert resp.status_code == 401


# ── /me ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_me_authenticated(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        reg = await client.post("/api/auth/register", json=citizen_payload)
        token = reg.json()["access_token"]

        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == citizen_payload["email"]
    assert data["full_name"] == citizen_payload["full_name"]
    assert data["role"] == "citizen"


@pytest.mark.asyncio
async def test_get_me_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalidtoken.abc.xyz"},
        )
    assert resp.status_code == 401


# ── Profile Update ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_me(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        reg = await client.post("/api/auth/register", json=citizen_payload)
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.put(
            "/api/auth/me",
            json={"full_name": "Updated Name"},
            headers=headers,
        )

    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Name"


# ── Change Password ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_change_password_success(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        reg = await client.post("/api/auth/register", json=citizen_payload)
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/auth/change-password",
            json={
                "current_password": citizen_payload["password"],
                "new_password": "newpassword2",
            },
            headers=headers,
        )
        assert resp.status_code == 204

        # Login with new password should succeed
        login_resp = await client.post("/api/auth/login", json={
            "email": citizen_payload["email"],
            "password": "newpassword2",
        })
        assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(citizen_payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        reg = await client.post("/api/auth/register", json=citizen_payload)
        token = reg.json()["access_token"]

        resp = await client.post(
            "/api/auth/change-password",
            json={"current_password": "WRONGOLD1", "new_password": "newpass123"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 400
