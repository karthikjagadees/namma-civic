"""Normalize supported channel payloads without changing citizen-authored text."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Protocol, Sequence

from app.channels.schemas import CanonicalReport
from app.models.complaint import ComplaintSource


class Geocoder(Protocol):
    """Async interface used to resolve an address or landmark to coordinates."""

    async def geocode_address(self, address: str) -> Optional[Mapping[str, Any]]:
        """Return provider location data, or None when no match is available."""


def _first(mapping: Mapping[str, Any], *keys: str) -> Any:
    """Return the first present non-empty value from mapping."""
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return None


def _nested(payload: Mapping[str, Any], parent: str, key: str) -> Any:
    """Read a value from an optional nested mapping."""
    value = payload.get(parent)
    return value.get(key) if isinstance(value, Mapping) else None


def _text_for(channel: ComplaintSource, payload: Mapping[str, Any]) -> str:
    """Extract the message text from the supported channel payload shapes."""
    if channel in (ComplaintSource.web, ComplaintSource.mobile):
        title = payload.get("title")
        description = payload.get("description")
        parts = [str(part).strip() for part in (title, description) if part and str(part).strip()]
        return "\n".join(parts)
    if channel == ComplaintSource.voice:
        return str(_first(payload, "transcript", "text") or "").strip()
    message_text = _nested(payload, "message", "text")
    return str(_first(payload, "text") or message_text or "").strip()


def _photo_urls(payload: Mapping[str, Any]) -> list[str]:
    """Collect photo references from common upload and messaging payload shapes."""
    values: Any = _first(payload, "photos", "media", "attachments") or []
    if isinstance(values, (str, Mapping)):
        values = [values]
    urls: list[str] = []
    if isinstance(values, Sequence):
        for item in values:
            if isinstance(item, str):
                urls.append(item)
            elif isinstance(item, Mapping):
                raw_type = item.get("media_type") or item.get("type") or "image"
                media_type = str(getattr(raw_type, "value", raw_type)).lower()
                if media_type not in {"image", "photo", "picture"}:
                    continue
                url = _first(item, "file_url", "url", "link")
                if url:
                    urls.append(str(url))
    return urls


def _parse_timestamp(value: Any) -> datetime:
    """Parse an ISO timestamp or use current UTC when the channel omits it."""
    if value is None or value == "":
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


async def normalize_report(
    channel: ComplaintSource,
    payload: Mapping[str, Any],
    *,
    geocoder: Optional[Geocoder] = None,
) -> CanonicalReport:
    """Convert a web, mobile, voice, or WhatsApp payload into canonical fields.

    Geocoding is only attempted when a complete coordinate pair is absent and an
    address or landmark is present. Inject a geocoder in tests and offline runs.
    """
    if not isinstance(channel, ComplaintSource):
        channel = ComplaintSource(channel)

    location = payload.get("location") if isinstance(payload.get("location"), Mapping) else {}
    latitude = _first(payload, "latitude", "lat")
    longitude = _first(payload, "longitude", "lon", "lng")
    latitude = latitude if latitude is not None else _first(location, "latitude", "lat")
    longitude = longitude if longitude is not None else _first(location, "longitude", "lon", "lng")
    address = _first(payload, "address") or _first(location, "address")
    landmark = _first(payload, "landmark") or _first(location, "landmark")
    language = _first(payload, "language", "language_code") or _nested(payload, "message", "language")
    reported_at = _first(payload, "reported_at", "timestamp") or _nested(payload, "message", "timestamp")
    contact = _first(payload, "reporter_contact", "phone", "from") or _nested(payload, "reporter", "phone")
    reporter_id = _first(payload, "reporter_id", "citizen_id") or _nested(payload, "reporter", "id")
    warnings: list[str] = []
    confidence: Optional[float] = _first(payload, "location_confidence")
    accuracy_m: Optional[float] = _first(payload, "location_accuracy_m")

    if (latitude is None) != (longitude is None):
        warnings.append("Incomplete coordinate pair ignored; provide both latitude and longitude.")
        latitude = longitude = None

    query = address or landmark
    if latitude is None and query:
        try:
            if geocoder is None:
                from app.gis.service import geocode_address

                result = await geocode_address(str(query))
            else:
                result = await geocoder.geocode_address(str(query))
            if result:
                latitude = result.get("latitude")
                longitude = result.get("longitude")
                address = result.get("formatted_address") or result.get("address") or address
                confidence = result.get("confidence")
                accuracy_m = result.get("accuracy_m") or result.get("accuracy")
                if (latitude is None) != (longitude is None):
                    latitude = longitude = None
                    warnings.append("Geocoder returned an incomplete coordinate pair.")
            else:
                warnings.append("Address or landmark could not be geocoded.")
        except Exception as exc:
            # Preserve the report; make the missing resolution visible to callers.
            warnings.append(f"Geocoding failed: {type(exc).__name__}.")

    return CanonicalReport(
        text=_text_for(channel, payload),
        latitude=latitude,
        longitude=longitude,
        address=address,
        landmark=landmark,
        photos=_photo_urls(payload),
        language=language,
        reporter_id=reporter_id,
        reporter_contact=contact,
        channel=channel,
        reported_at=_parse_timestamp(reported_at),
        location_confidence=confidence,
        location_accuracy_m=accuracy_m,
        normalization_warnings=warnings,
    )
