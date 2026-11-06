"""Tests for normalization of reports received from supported channels."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.complaint import ComplaintSource, MediaType
from app.channels import normalize_report


class FakeGeocoder:
    """Deterministic geocoder used to keep channel tests offline."""

    async def geocode_address(self, query: str):
        assert query == "Central Park gate"
        return {
            "latitude": 12.97,
            "longitude": 77.59,
            "formatted_address": "Central Park gate, Bengaluru",
            "confidence": 0.72,
            "accuracy_m": 80,
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("channel", "payload", "expected_text", "expected_contact", "expected_photos"),
    [
        (
            ComplaintSource.web,
            {"title": "Streetlight", "description": "Light is out", "source": "web"},
            "Streetlight\nLight is out",
            None,
            [],
        ),
        (
            ComplaintSource.mobile,
            {"title": "Road", "description": "Pothole near school", "photos": ["/p.jpg"]},
            "Road\nPothole near school",
            None,
            ["/p.jpg"],
        ),
        (
            ComplaintSource.voice,
            {"transcript": "Yahan bada gaddha hai", "phone": "+919900000001", "attachments": [{"url": "/voice-photo.jpg", "type": "image"}]},
            "Yahan bada gaddha hai",
            "+919900000001",
            ["/voice-photo.jpg"],
        ),
        (
            ComplaintSource.whatsapp,
            {"message": {"text": "குப்பை அகற்றப்படவில்லை", "timestamp": "2026-01-02T03:04:05Z"}, "from": "+919900000002"},
            "குப்பை அகற்றப்படவில்லை",
            "+919900000002",
            [],
        ),
    ],
)
async def test_each_channel_maps_to_canonical_report(channel, payload, expected_text, expected_contact, expected_photos):
    report = await normalize_report(channel, payload)

    assert report.channel == channel
    assert report.text == expected_text
    assert report.reporter_contact == expected_contact
    assert report.photos == expected_photos
    assert report.reported_at.tzinfo is not None


@pytest.mark.asyncio
async def test_rough_landmark_is_geocoded_with_provider_uncertainty():
    report = await normalize_report(
        ComplaintSource.voice,
        {"transcript": "Road is damaged", "landmark": "Central Park gate"},
        geocoder=FakeGeocoder(),
    )

    assert (report.latitude, report.longitude) == (12.97, 77.59)
    assert report.address == "Central Park gate, Bengaluru"
    assert report.location_confidence == 0.72
    assert report.location_accuracy_m == 80


@pytest.mark.asyncio
async def test_anonymous_report_and_missing_location_are_preserved_without_guessing():
    report = await normalize_report(ComplaintSource.web, {"description": "Overflowing bin"})

    assert report.reporter_id is None
    assert report.reporter_contact is None
    assert report.latitude is None and report.longitude is None
    assert report.location_confidence is None
    assert report.photos == []


@pytest.mark.asyncio
async def test_malformed_coordinates_are_rejected():
    with pytest.raises(ValidationError):
        await normalize_report(
            ComplaintSource.mobile,
            {"description": "Road issue", "latitude": 120, "longitude": 40},
        )


@pytest.mark.asyncio
async def test_geocoder_failure_keeps_report_and_records_warning():
    class BrokenGeocoder:
        async def geocode_address(self, query: str):
            raise RuntimeError("offline")

    report = await normalize_report(
        ComplaintSource.voice,
        {"transcript": "Road is damaged", "address": "Central Park gate"},
        geocoder=BrokenGeocoder(),
    )

    assert report.latitude is None and report.longitude is None
    assert report.normalization_warnings
    assert "geocod" in report.normalization_warnings[0].lower()


@pytest.mark.asyncio
async def test_report_timestamp_is_preserved():
    timestamp = datetime(2026, 2, 3, 4, 5, tzinfo=timezone.utc)
    report = await normalize_report(
        ComplaintSource.mobile,
        {"description": "Broken drain", "reported_at": timestamp},
    )
    assert report.reported_at == timestamp


@pytest.mark.asyncio
async def test_existing_media_upload_shape_keeps_images_and_skips_audio():
    report = await normalize_report(
        ComplaintSource.web,
        {
            "description": "Blocked drain",
            "media": [
                {"file_url": "/image.jpg", "media_type": MediaType.image},
                {"file_url": "/note.wav", "media_type": MediaType.audio},
            ],
        },
    )

    assert report.photos == ["/image.jpg"]
