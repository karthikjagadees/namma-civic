"""
Namma Civic — Complaint Schemas
Pydantic v2 validation models for complaints, media, and timeline.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.complaint import (
    ComplaintCategory,
    ComplaintSource,
    ComplaintStatus,
    MediaType,
    PriorityLevel,
)
from app.schemas.ai import ComplaintAIAnalysisRecord


class MediaUploadItem(BaseModel):
    file_url: str
    file_name: str
    file_size: int = 0
    mime_type: str = "image/jpeg"
    media_type: MediaType = MediaType.image
    caption: Optional[str] = None


class ComplaintCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    category: ComplaintCategory = ComplaintCategory.other
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    address: Optional[str] = Field(None, max_length=500)
    landmark: Optional[str] = Field(None, max_length=255)
    location_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    location_accuracy_m: Optional[float] = Field(None, ge=0.0)
    source: ComplaintSource = ComplaintSource.web
    media: Optional[List[MediaUploadItem]] = []


class ComplaintUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, min_length=5)
    category: Optional[ComplaintCategory] = None
    status: Optional[ComplaintStatus] = None
    priority: Optional[PriorityLevel] = None
    severity: Optional[int] = Field(None, ge=1, le=10)
    department_id: Optional[str] = None
    assigned_officer_id: Optional[str] = None
    note: Optional[str] = None  # Added to timeline audit


class ComplaintMediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    media_type: MediaType
    file_url: str
    file_name: str
    file_size: int
    mime_type: str
    caption: Optional[str] = None
    is_resolution_evidence: bool = False
    created_at: datetime


class ComplaintTimelineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: ComplaintStatus
    changed_by_id: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tracking_id: str
    citizen_id: str
    title: str
    description: str
    category: ComplaintCategory
    status: ComplaintStatus
    priority: PriorityLevel
    severity: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    landmark: Optional[str] = None
    location_confidence: Optional[float] = None
    location_accuracy_m: Optional[float] = None
    department_id: Optional[str] = None
    assigned_officer_id: Optional[str] = None
    source: ComplaintSource
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    media: List[ComplaintMediaOut] = []
    timeline: List[ComplaintTimelineOut] = []
    ai_analysis: Optional[ComplaintAIAnalysisRecord] = None


class ComplaintListResponse(BaseModel):
    items: List[ComplaintOut]
    total: int
    page: int
    limit: int
    pages: int


class UploadMediaResponse(BaseModel):
    file_url: str
    file_name: str
    file_size: int
    mime_type: str
    media_type: MediaType
