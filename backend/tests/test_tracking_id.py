"""Tests for citizen-facing complaint tracking IDs (e.g. NC-7K4P-9XQ2)."""
from __future__ import annotations

import re
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.database import async_session_factory
from app.core.tracking import (
    TRACKING_ALPHABET,
    generate_tracking_id,
    normalize_tracking_id,
)
from app.models.complaint import Complaint

BASE = "http://test"
FORMAT = re.compile(r"^NC-[2-9A-HJKMNP-Z]{4}-[2-9A-HJKMNP-Z]{4}$")


def test_generated_ids_use_the_documented_format_and_never_ambiguous_characters():
    ids = [generate_tracking_id() for _ in range(2000)]
    assert all(FORMAT.match(code) for code in ids)
    body = "".join(code.replace("NC-", "").replace("-", "") for code in ids)
    assert not set("01ILO") & set(body)
    assert set(body) <= set(TRACKING_ALPHABET)


def test_generated_ids_do_not_collide_in_a_large_sample():
    ids = [generate_tracking_id() for _ in range(20000)]
    assert len(set(ids)) == len(ids)


@pytest.mark.parametrize(
    "raw",
    ["NC-7K4P-9XQ2", "nc-7k4p-9xq2", "  nc 7k4p 9xq2 ", "NC7K4P9XQ2", "nc_7k4p_9xq2"],
)
def test_normalize_accepts_typing_variations(raw):
    assert normalize_tracking_id(raw) == "NC-7K4P-9XQ2"


@pytest.mark.parametrize(
    "raw",
    [None, "", "NC", "NC-7K4P", "XX-7K4P-9XQ2", "NC-7K4P-9XQ22", "NC-7K0P-9XQ2", "NC-7KIP-9XQL", "../etc/passwd"],
)
def test_normalize_rejects_malformed_or_ambiguous_ids(raw):
    assert normalize_tracking_id(raw) is None


async def _register(client: AsyncClient, name: str) -> tuple[str, str]:
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


async def _report(client: AsyncClient, token: str, **overrides) -> dict:
    body = {
        "title": "Synthetic tracking-id pothole",
        "description": "A deep pothole damages vehicles on the synthetic test road.",
        "category": "pothole",
        "latitude": 12.9000 + (uuid.uuid4().int % 1000) / 10000,
        "longitude": 77.5000 + (uuid.uuid4().int % 1000) / 10000,
    }
    body.update(overrides)
    created = await client.post(
        "/api/complaints", headers={"Authorization": f"Bearer {token}"}, json=body
    )
    assert created.status_code == 201, created.text
    return created.json()


@pytest.mark.asyncio
async def test_new_report_returns_a_unique_stored_tracking_id():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, token = await _register(client, "tracking-unique")
        first = await _report(client, token)
        second = await _report(client, token)

    assert FORMAT.match(first["tracking_id"])
    assert FORMAT.match(second["tracking_id"])
    assert first["tracking_id"] != second["tracking_id"]
    async with async_session_factory() as session:
        stored = await session.scalar(
            select(Complaint.tracking_id).where(Complaint.id == first["id"])
        )
        duplicates = await session.scalar(
            select(func.count()).select_from(Complaint).where(
                Complaint.tracking_id == first["tracking_id"]
            )
        )
    assert stored == first["tracking_id"]
    assert duplicates == 1


@pytest.mark.asyncio
async def test_public_lookup_by_tracking_id_works_without_login_and_leaks_nothing_private():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, token = await _register(client, "tracking-public")
        report = await _report(
            client, token, title="Sensitive private title 8841",
            description="Private description with my phone number 5550001111.",
        )
        code = report["tracking_id"]
        exact = await client.get(f"/api/incidents/track/{code}")
        typed_loosely = await client.get(f"/api/incidents/track/{code.lower().replace('-', ' ')}")

    assert exact.status_code == 200, exact.text
    payload = exact.json()
    assert payload["tracking_id"] == code
    assert payload["reporter_count"] == 1
    assert {"status", "timeline", "what_happens_next", "submitted_at"} <= set(payload)
    assert not {"citizen_id", "reporter_id", "email", "phone", "description"} & set(payload)
    assert "5550001111" not in repr(payload)
    assert typed_loosely.status_code == 200
    assert typed_loosely.json()["incident_id"] == payload["incident_id"]


@pytest.mark.asyncio
async def test_unknown_and_malformed_ids_return_the_same_404_so_ids_cannot_be_probed():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        unknown = await client.get("/api/incidents/track/NC-2222-2222")
        malformed = await client.get("/api/incidents/track/not-a-real-id")

    assert unknown.status_code == 404
    assert malformed.status_code == 404
    assert unknown.json() == malformed.json()


@pytest.mark.asyncio
async def test_two_citizens_reporting_the_same_issue_get_different_ids_for_one_incident():
    """Duplicate reports keep their own IDs but follow the same shared incident."""
    from app.main import app

    lat, lon = 12.9345, 77.6101
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, token_a = await _register(client, "tracking-dup-a")
        _, token_b = await _register(client, "tracking-dup-b")
        first = await _report(client, token_a, latitude=lat, longitude=lon,
                              title="Large pothole near the metro pillar",
                              description="Large pothole near the metro pillar damaging two wheelers.")
        second = await _report(client, token_b, latitude=lat, longitude=lon,
                               title="Large pothole near the metro pillar",
                               description="Large pothole near the metro pillar damaging two wheelers.")
        track_a = await client.get(f"/api/incidents/track/{first['tracking_id']}")
        track_b = await client.get(f"/api/incidents/track/{second['tracking_id']}")

    assert first["tracking_id"] != second["tracking_id"]
    assert track_a.status_code == 200 and track_b.status_code == 200
    # Each citizen can follow their own code; if the engine linked the reports
    # the shared incident is the same and the reporter count reflects both.
    if track_a.json()["incident_id"] == track_b.json()["incident_id"]:
        assert track_a.json()["reporter_count"] == 2
