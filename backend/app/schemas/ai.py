"""
Namma Civic — AI Schemas
Pydantic schemas for AI intake, multimodal analysis, and explainability.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AIAnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=3, description="Citizen grievance or description")
    image_url: Optional[str] = Field(None, description="URL or local path to uploaded image")
    audio_url: Optional[str] = Field(None, description="URL or local path to voice recording")
    category_hint: Optional[str] = Field(None, description="Citizen pre-selected category hint")


class VisionAnalysisSchema(BaseModel):
    has_damage_detected: bool
    detected_damage_type: str
    visual_severity_estimate: int = Field(..., ge=1, le=10)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    visual_features: List[str] = []
    safety_hazard_level: str = "medium"
    details: Dict[str, Any] = {}


class AIAnalysisResponse(BaseModel):
    summary: str
    detected_category: str
    confidence_score: float
    urgency_score: float
    severity: int
    recommended_department: str
    reasoning: str
    extracted_entities: Dict[str, Any] = {}
    vision_analysis: Optional[VisionAnalysisSchema] = None
    provider_used: str = "mock"
    model_used: str = "rule-heuristic-v1"
    processing_time_ms: int = 0


class ComplaintAIAnalysisRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    complaint_id: str
    summary: str
    detected_category: str
    confidence_score: float
    urgency_score: float
    severity: int
    recommended_department: str
    reasoning: str
    extracted_entities: Dict[str, Any] = {}
    vision_analysis: Optional[Dict[str, Any]] = None
    provider_used: str
    model_used: str
    processing_time_ms: int
    created_at: datetime
    updated_at: datetime
