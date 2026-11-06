"""Tests for local perceptual photo hashing and persistence/backfill support."""
from PIL import Image, ImageDraw
import pytest
from sqlalchemy import create_engine, text

from app.deduplication.images import compute_phash, phash_similarity


def test_phash_is_stable_for_same_image_and_nearby_for_resized_copy(tmp_path):
    original = Image.new("RGB", (80, 80), "white")
    draw = ImageDraw.Draw(original)
    draw.rectangle((16, 18, 54, 60), fill="black")
    source = tmp_path / "source.png"
    resized = tmp_path / "resized.png"
    original.save(source)
    original.resize((140, 140)).save(resized)

    first = compute_phash(source)
    same = compute_phash(source)
    near = compute_phash(resized)

    assert first == same
    assert phash_similarity(first, near) >= 0.75


def test_phash_returns_none_for_unreadable_or_missing_file(tmp_path):
    bad_file = tmp_path / "bad.jpg"
    bad_file.write_text("not an image")

    assert compute_phash(bad_file) is None
    assert compute_phash(tmp_path / "missing.jpg") is None


def test_complaint_media_stores_nullable_phash_and_incident_has_recurrence_link():
    from app.models.complaint import ComplaintMedia
    from app.models.incident import Incident
    from app.schemas.complaint import ComplaintCreateRequest

    media = ComplaintMedia(complaint_id="complaint", file_url="/uploads/photo.jpg", perceptual_hash=None)
    incident = Incident(title="Issue", category="pothole", recurrence_of_incident_id="prior-incident")
    report = ComplaintCreateRequest(
        title="Street damage", description="Road surface is damaged",
        location_confidence=0.7, location_accuracy_m=55.0,
    )

    assert media.perceptual_hash is None
    assert incident.recurrence_of_incident_id == "prior-incident"
    assert report.location_confidence == 0.7
    assert report.location_accuracy_m == 55.0


def test_migration_backfills_hashes_for_accessible_legacy_photos(tmp_path):
    import importlib.util
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parents[1]
    migration_path = backend_dir / "migrations" / "versions" / "0003_duplicate_detection.py"
    spec = importlib.util.spec_from_file_location("phase3_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    image_path = tmp_path / "old-photo.png"
    Image.new("RGB", (32, 32), "white").save(image_path)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE complaint_media (id TEXT PRIMARY KEY, file_url TEXT, media_type TEXT, perceptual_hash TEXT)"
        ))
        connection.execute(text(
            "INSERT INTO complaint_media (id, file_url, media_type) VALUES ('m1', '/uploads/old-photo.png', 'image')"
        ))
        connection.execute(text(
            "INSERT INTO complaint_media (id, file_url, media_type) VALUES ('m2', '/uploads/missing.png', 'image')"
        ))

        processed = migration.backfill_media_hashes(connection, tmp_path)
        hashes = connection.execute(text("SELECT id, perceptual_hash FROM complaint_media ORDER BY id")).all()

    assert processed == 1
    assert hashes[0][1]
    assert hashes[1][1] is None


@pytest.mark.asyncio
async def test_new_complaint_media_persists_hash_of_local_uploaded_photo(tmp_path, monkeypatch):
    from sqlalchemy import select

    from app.core.config import settings
    from app.core.database import async_session_factory
    from app.models.user import User
    from app.schemas.complaint import ComplaintCreateRequest, MediaUploadItem
    from app.services.complaint_service import ComplaintService

    Image.new("RGB", (48, 48), "gray").save(tmp_path / "new-photo.png")
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    async with async_session_factory() as session:
        citizen = await session.scalar(select(User).where(User.email == "citizen@demo.namma-civic.ai"))
        assert citizen is not None
        data = ComplaintCreateRequest(
            title="Broken drain",
            description="Drain cover is missing",
            location_confidence=0.8,
            location_accuracy_m=25.0,
            media=[MediaUploadItem(file_url="/uploads/new-photo.png", file_name="new-photo.png")],
        )
        complaint = await ComplaintService(session).create_complaint(data, citizen.id)
        assert complaint.media[0].perceptual_hash
        assert complaint.location_confidence == 0.8
        assert complaint.location_accuracy_m == 25.0
        await session.rollback()
