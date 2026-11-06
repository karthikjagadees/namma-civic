"""Print a report-only duplicate threshold recommendation from officer labels."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
import json

from sqlalchemy import select

from app.core.database import async_session_factory
from app.deduplication.engine import Thresholds
from app.deduplication.officer_calibration import recommend_thresholds
from app.models.duplicate_review import DuplicateReviewDecision


async def main() -> None:
    """Read adjudicated pair labels and print current-versus-proposed settings."""
    async with async_session_factory() as session:
        decisions = list((await session.scalars(
            select(DuplicateReviewDecision)
            .where(DuplicateReviewDecision.candidate_incident_id.is_not(None))
            .order_by(DuplicateReviewDecision.created_at.desc(), DuplicateReviewDecision.id.desc())
        )).all())
    latest = {}
    for row in decisions:
        latest.setdefault((row.complaint_id, row.candidate_incident_id, row.officer_id), row)
    labels = [(row.score, row.is_duplicate) for row in latest.values() if row.score is not None]
    recommendation = recommend_thresholds(labels, Thresholds())
    print(json.dumps({
        "label_source": "persisted officer review decisions",
        "labeled_pair_count": recommendation.labeled_pair_count,
        "current_thresholds": asdict(recommendation.current),
        "proposed_thresholds": asdict(recommendation.proposed),
        "auto_metrics_on_labels": asdict(recommendation.auto_metrics),
        "review_metrics_on_labels": asdict(recommendation.review_metrics),
        "applied": recommendation.applied,
        "note": "Recommendation only; no runtime setting or threshold was changed.",
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
