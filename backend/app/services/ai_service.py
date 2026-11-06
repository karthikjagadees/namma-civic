"""
Namma Civic — AI Service Layer
Orchestrates multimodal ingestion, automated triage, and complaint enrichment.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.ai.factory import get_ai_provider
from app.models.ai_analysis import AIAnalysis
from app.models.complaint import (
    Complaint,
    ComplaintCategory,
    ComplaintStatus,
    MediaType,
    PriorityLevel,
    ComplaintTimeline,
)
from app.models.department import Department
from app.schemas.ai import AIAnalyzeRequest, AIAnalysisResponse

logger = logging.getLogger("namma-civic.service.ai")

CATEGORY_TO_DEPT_CODE = {
    # Snake case
    "pothole": "ROADS",
    "garbage": "SANITATION",
    "water_leakage": "WATER",
    "street_light": "ELECTRICAL",
    "drainage": "DRAINAGE",
    "traffic_signal": "ROADS",
    "encroachment": "PUBLIC_WORKS",
    "other": "PUBLIC_WORKS",
    # Uppercase
    "ROADS": "ROADS",
    "SANITATION": "SANITATION",
    "WATER_SUPPLY": "WATER",
    "WATER": "WATER",
    "STREETLIGHTS": "ELECTRICAL",
    "ELECTRICAL": "ELECTRICAL",
    "DRAINAGE": "DRAINAGE",
    "PARKS": "PARKS",
    "TRAFFIC": "ROADS",
    "PUBLIC_HEALTH": "HEALTH",
    "OTHER": "PUBLIC_WORKS",
}

AI_CATEGORY_TO_COMPLAINT_CATEGORY = {
    "pothole": ComplaintCategory.pothole,
    "garbage": ComplaintCategory.garbage,
    "water_leakage": ComplaintCategory.water_leakage,
    "street_light": ComplaintCategory.street_light,
    "drainage": ComplaintCategory.drainage,
    "traffic_signal": ComplaintCategory.traffic_signal,
    "encroachment": ComplaintCategory.encroachment,
    "other": ComplaintCategory.other,
    "roads": ComplaintCategory.pothole,
    "sanitation": ComplaintCategory.garbage,
    "water_supply": ComplaintCategory.water_leakage,
    "water": ComplaintCategory.water_leakage,
    "streetlights": ComplaintCategory.street_light,
    "electrical": ComplaintCategory.street_light,
    "traffic": ComplaintCategory.traffic_signal,
    "parks": ComplaintCategory.encroachment,
    "ROADS": ComplaintCategory.pothole,
    "SANITATION": ComplaintCategory.garbage,
    "WATER_SUPPLY": ComplaintCategory.water_leakage,
    "WATER": ComplaintCategory.water_leakage,
    "STREETLIGHTS": ComplaintCategory.street_light,
    "ELECTRICAL": ComplaintCategory.street_light,
    "DRAINAGE": ComplaintCategory.drainage,
    "TRAFFIC": ComplaintCategory.traffic_signal,
    "PARKS": ComplaintCategory.encroachment,
    "OTHER": ComplaintCategory.other,
}


class AIService:
    @staticmethod
    async def analyze_raw_payload(payload: AIAnalyzeRequest) -> AIAnalysisResponse:
        """Run standalone multimodal triage on arbitrary user text and media."""
        provider = get_ai_provider()
        result = await provider.synthesize_multimodal_triage(
            text=payload.text,
            image_url=payload.image_url,
            audio_url=payload.audio_url,
            category_hint=payload.category_hint,
        )

        vision_dict = None
        if result.vision_analysis:
            vision_dict = result.vision_analysis

        return AIAnalysisResponse(
            summary=result.summary,
            detected_category=result.detected_category,
            confidence_score=result.confidence_score,
            urgency_score=result.urgency_score,
            severity=result.severity,
            recommended_department=result.recommended_department,
            reasoning=result.reasoning,
            extracted_entities=result.extracted_entities,
            vision_analysis=vision_dict,
            provider_used=result.provider_name,
            model_used=result.model_name,
            processing_time_ms=result.processing_time_ms,
        )

    @staticmethod
    async def analyze_and_enrich_complaint(
        complaint_id: str,
        session: AsyncSession,
        re_analyze: bool = False,
    ) -> Optional[AIAnalysis]:
        """
        Run AI triage on an existing complaint, save AIAnalysis record,
        update complaint category, severity, priority, and append timeline entry.
        """
        stmt = (
            select(Complaint)
            .where(Complaint.id == complaint_id)
            .options(
                selectinload(Complaint.media),
                selectinload(Complaint.timeline),
                selectinload(Complaint.ai_analysis),
            )
        )
        res = await session.execute(stmt)
        complaint = res.scalar_one_or_none()
        if not complaint:
            logger.warning(f"Complaint {complaint_id} not found for AI analysis.")
            return None

        # Return existing if not forcing re-analysis
        if complaint.ai_analysis and not re_analyze:
            return complaint.ai_analysis

        # Find first image and audio media if present
        image_url = None
        audio_url = None
        for m in complaint.media:
            if m.media_type == MediaType.image and not image_url:
                image_url = m.file_url
            elif m.media_type == MediaType.audio and not audio_url:
                audio_url = m.file_url

        # Synthesize combined text description
        full_text = f"{complaint.title}\n{complaint.description}"
        if complaint.landmark:
            full_text += f"\nLandmark: {complaint.landmark}"
        if complaint.address:
            full_text += f"\nAddress: {complaint.address}"

        provider = get_ai_provider()
        result = await provider.synthesize_multimodal_triage(
            text=full_text,
            image_url=image_url,
            audio_url=audio_url,
            category_hint=complaint.category.value if complaint.category else None,
        )

        # Resolve priority based on urgency and severity
        if result.severity >= 8 or result.urgency_score >= 0.85:
            new_priority = PriorityLevel.critical
        elif result.severity >= 6 or result.urgency_score >= 0.65:
            new_priority = PriorityLevel.high
        elif result.severity >= 4:
            new_priority = PriorityLevel.medium
        else:
            new_priority = PriorityLevel.low

        # Resolve department routing
        dept_code = CATEGORY_TO_DEPT_CODE.get(result.detected_category, CATEGORY_TO_DEPT_CODE.get(result.detected_category.upper(), "PUBLIC_WORKS"))
        dept_stmt = select(Department).where(Department.code == dept_code)
        dept_res = await session.execute(dept_stmt)
        matched_dept = dept_res.scalar_one_or_none()

        # Update complaint fields
        complaint.severity = result.severity
        complaint.priority = new_priority
        if matched_dept and not complaint.department_id:
            complaint.department_id = matched_dept.id

        # Update category if complaint was generic or unclassified
        if complaint.category == ComplaintCategory.other:
            mapped_cat = (
                AI_CATEGORY_TO_COMPLAINT_CATEGORY.get(result.detected_category)
                or AI_CATEGORY_TO_COMPLAINT_CATEGORY.get(result.detected_category.lower())
                or AI_CATEGORY_TO_COMPLAINT_CATEGORY.get(result.detected_category.upper())
            )
            if mapped_cat:
                complaint.category = mapped_cat

        if complaint.status == ComplaintStatus.pending:
            complaint.status = ComplaintStatus.verified

        # Create or update AIAnalysis record
        ai_record = complaint.ai_analysis
        if not ai_record:
            ai_record = AIAnalysis(
                complaint_id=complaint.id,
                summary=result.summary,
                detected_category=result.detected_category,
                confidence_score=result.confidence_score,
                urgency_score=result.urgency_score,
                severity=result.severity,
                recommended_department=result.recommended_department,
                reasoning=result.reasoning,
                extracted_entities=result.extracted_entities,
                vision_analysis=result.vision_analysis,
                provider_used=result.provider_name,
                model_used=result.model_name,
                processing_time_ms=result.processing_time_ms,
            )
            session.add(ai_record)
        else:
            ai_record.summary = result.summary
            ai_record.detected_category = result.detected_category
            ai_record.confidence_score = result.confidence_score
            ai_record.urgency_score = result.urgency_score
            ai_record.severity = result.severity
            ai_record.recommended_department = result.recommended_department
            ai_record.reasoning = result.reasoning
            ai_record.extracted_entities = result.extracted_entities
            ai_record.vision_analysis = result.vision_analysis
            ai_record.provider_used = result.provider_name
            ai_record.model_used = result.model_name
            ai_record.processing_time_ms = result.processing_time_ms

        # Audit timeline entry
        timeline_entry = ComplaintTimeline(
            complaint_id=complaint.id,
            status=complaint.status,
            changed_by_id=None,
            note=(
                f"Autonomous AI Multimodal Intake Analysis by {result.provider_name} ({result.model_name}). "
                f"Detected: {result.detected_category} with {int(result.confidence_score * 100)}% confidence. "
                f"Severity: {result.severity}/10, Urgency: {int(result.urgency_score * 100)}%."
            ),
        )
        session.add(timeline_entry)

        await session.commit()
        await session.refresh(ai_record)
        return ai_record
