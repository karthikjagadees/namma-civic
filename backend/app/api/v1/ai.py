"""
Namma Civic — AI Intake & Analysis Endpoints
Provides autonomous triage, computer vision inspection, and complaint AI record retrieval.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, OptionalUser, require_complaint_access
from app.core.database import get_db
from app.models.ai_analysis import AIAnalysis
from app.models.user import User
from app.schemas.ai import (
    AIAnalysisResponse,
    AIAnalyzeRequest,
    ComplaintAIAnalysisRecord,
)
from app.services.ai_service import AIService

logger = logging.getLogger("namma-civic.api.ai")

router = APIRouter(prefix="/ai", tags=["AI Intake & Understanding"])


@router.post("/analyze", response_model=AIAnalysisResponse, status_code=status.HTTP_200_OK)
async def analyze_report_payload(
    payload: AIAnalyzeRequest,
    current_user: OptionalUser,
) -> AIAnalysisResponse:
    """
    Run standalone multimodal AI triage on arbitrary text and media evidence.
    Available to citizens, visitors, or automated systems.
    """
    try:
        return await AIService.analyze_raw_payload(payload)
    except Exception as exc:
        logger.error(f"Error during AI analysis: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI analysis failed: {str(exc)}",
        )


@router.get("/analysis/{complaint_id}", response_model=ComplaintAIAnalysisRecord, status_code=status.HTTP_200_OK)
async def get_complaint_ai_analysis(
    complaint_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ComplaintAIAnalysisRecord:
    """
    Fetch the AI triage record for a specific complaint.
    """
    await require_complaint_access(db, complaint_id, current_user)
    stmt = select(AIAnalysis).where(AIAnalysis.complaint_id == complaint_id)
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI analysis not found for complaint {complaint_id}",
        )
    return ComplaintAIAnalysisRecord.model_validate(record)


@router.post("/reanalyze/{complaint_id}", response_model=ComplaintAIAnalysisRecord, status_code=status.HTTP_200_OK)
async def reanalyze_complaint(
    complaint_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ComplaintAIAnalysisRecord:
    """
    Trigger or re-trigger AI triage for an existing complaint.
    Enriches priority, severity, department routing, and logs an audit timeline entry.
    """
    await require_complaint_access(db, complaint_id, current_user)
    record = await AIService.analyze_and_enrich_complaint(complaint_id, db, re_analyze=True)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint {complaint_id} not found",
        )
    return ComplaintAIAnalysisRecord.model_validate(record)
