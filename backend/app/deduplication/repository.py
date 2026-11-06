"""Bounded database candidate retrieval kept outside the pure matching engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import math
from typing import Optional

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deduplication.engine import (
    CATEGORY_RADIUS_M,
    CandidateIncident,
    MatchDecision,
    MatchResult,
    ReportEvidence,
    Thresholds,
    match_report,
)
from app.models.complaint import Complaint, ComplaintStatus
from app.models.incident import Incident, IncidentStatus
from app.models.report_link import ReportLink


MAX_CANDIDATES = 250
SEARCH_WINDOW_DAYS = 365
METERS_PER_LATITUDE_DEGREE = 111_320.0


@dataclass(frozen=True)
class CandidateRetrieval:
    """Bounded incident candidates and whether the retrieval cap was reached."""

    candidates: tuple[CandidateIncident, ...]
    capped: bool = False


def _location_bounds(latitude: float, longitude: float, radius_m: float) -> tuple[float, float, float, float]:
    """Convert a meter radius to a conservative latitude/longitude bounding box."""
    lat_delta = radius_m / METERS_PER_LATITUDE_DEGREE
    cosine = max(abs(math.cos(math.radians(latitude))), 0.01)
    lon_delta = min(180.0, radius_m / (METERS_PER_LATITUDE_DEGREE * cosine))
    return (
        max(-90.0, latitude - lat_delta), min(90.0, latitude + lat_delta),
        max(-180.0, longitude - lon_delta), min(180.0, longitude + lon_delta),
    )


async def retrieve_candidate_incidents(
    session: AsyncSession,
    report: ReportEvidence,
    *,
    limit: int = MAX_CANDIDATES,
) -> CandidateRetrieval:
    """Fetch nearby active/recently resolved incidents using SQL bounds and a cap.

    Reports without coordinates are deliberately not searched by text alone.
    They are sent to review by `match_report` because location is unresolved.
    """
    if report.latitude is None or report.longitude is None:
        return CandidateRetrieval(())

    base_radius = CATEGORY_RADIUS_M.get(report.category, CATEGORY_RADIUS_M["other"])
    report_uncertainty = min(report.location_accuracy_m or 0.0, base_radius)
    bounds = _location_bounds(
        report.latitude,
        report.longitude,
        base_radius + report_uncertainty + base_radius,
    )
    minimum_lat, maximum_lat, minimum_lon, maximum_lon = bounds
    cutoff = report.reported_at - timedelta(days=SEARCH_WINDOW_DAYS)
    incidents_with_other_reports = exists(
        select(ReportLink.id).where(
            ReportLink.incident_id == Incident.id,
            ReportLink.is_active.is_(True),
            ReportLink.complaint_id != report.report_id,
        )
    )
    stmt = (
        select(Incident)
        .options(
            selectinload(Incident.report_links)
            .selectinload(ReportLink.complaint)
            .selectinload(Complaint.media)
        )
        .where(
            incidents_with_other_reports,
            Incident.status.in_((IncidentStatus.open, IncidentStatus.in_progress, IncidentStatus.resolved)),
            Incident.updated_at >= cutoff,
            Incident.latitude.between(minimum_lat, maximum_lat),
            Incident.longitude.between(minimum_lon, maximum_lon),
        )
        .order_by(Incident.created_at.desc(), Incident.id)
        .limit(limit + 1)
    )
    rows = list((await session.execute(stmt)).scalars().unique())
    capped = len(rows) > limit
    rows = rows[:limit]

    candidates: list[CandidateIncident] = []
    for incident in rows:
        linked_reports = [
            link.complaint for link in incident.report_links
            if link.is_active and link.complaint and link.complaint.id != report.report_id
        ]
        texts = tuple(
            text
            for complaint in linked_reports
            for text in (complaint.title, complaint.description)
            if text
        )
        hashes = tuple(
            media.perceptual_hash
            for complaint in linked_reports
            for media in complaint.media
            if media.media_type.value == "image" and media.perceptual_hash
        )
        last_reported_at = max(
            (complaint.created_at for complaint in linked_reports),
            default=incident.created_at,
        )
        candidates.append(
            CandidateIncident(
                incident_id=incident.id,
                title=incident.title,
                report_texts=texts,
                category=incident.category.value,
                status=incident.status.value,
                latitude=incident.latitude,
                longitude=incident.longitude,
                location_confidence=incident.location_confidence,
                address=incident.address,
                landmark=incident.landmark,
                location_accuracy_m=incident.location_accuracy_m,
                photo_hashes=hashes,
                created_at=incident.created_at,
                last_reported_at=last_reported_at,
            )
        )
    return CandidateRetrieval(tuple(candidates), capped)


async def resolve_report_against_incidents(
    session: AsyncSession,
    report: ReportEvidence,
    *,
    thresholds: Optional[Thresholds] = None,
    candidate_limit: int = MAX_CANDIDATES,
) -> MatchResult:
    """Retrieve bounded candidates, score them, and fail closed on retrieval errors."""
    try:
        retrieval = await retrieve_candidate_incidents(session, report, limit=candidate_limit)
        if retrieval.capped:
            return MatchResult(
                MatchDecision.officer_review,
                reasons=("Candidate limit was reached; review is required to avoid an incomplete search.",),
                failures=(f"candidate_limit_exceeded:{candidate_limit}",),
            )
        return match_report(report, retrieval.candidates, thresholds or Thresholds())
    except Exception as exc:
        return MatchResult(
            MatchDecision.officer_review,
            reasons=("Incident candidate retrieval failed; officer review is required.",),
            failures=(f"{type(exc).__name__}: candidate retrieval failed",),
        )
