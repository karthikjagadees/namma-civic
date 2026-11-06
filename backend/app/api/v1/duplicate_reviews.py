"""Officer-only duplicate review queue and audited decisions."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import DBSession, RequireOfficer
from app.services.duplicate_review_service import DuplicateReviewService

router = APIRouter(prefix="/officer/duplicate-reviews", tags=["Officer duplicate review"])


class DuplicateReviewAction(BaseModel):
    """Officer resolution action for one pending candidate review."""

    action: Literal["confirm_link", "reject_match", "merge_incidents", "split_report"]
    candidate_incident_id: Optional[str] = None
    note: str = Field(..., min_length=3, max_length=2000)


@router.get("")
async def list_duplicate_reviews(
    officer: RequireOfficer,
    db: DBSession,
    limit: int = Query(100, ge=1, le=300),
):
    """Return pending grey-zone reports with candidate evidence for comparison."""
    return await DuplicateReviewService.list_queue(db, limit=limit)


@router.post("/{review_id}/decision")
async def decide_duplicate_review(
    review_id: str,
    payload: DuplicateReviewAction,
    officer: RequireOfficer,
    db: DBSession,
):
    """Apply a review decision with an immutable officer label and audit event."""
    try:
        return await DuplicateReviewService.decide(
            db,
            review_id,
            officer.id,
            action=payload.action,
            candidate_incident_id=payload.candidate_incident_id,
            note=payload.note,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
