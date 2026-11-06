"""
Namma Civic — AI Analysis Model
Records multimodal intake analysis, computer vision damage metrics, confidence scores, and explainable AI reasoning.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AIAnalysis(Base):
    """
    Multimodal intake analysis results for a civic complaint.
    """
    __tablename__ = "ai_analyses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    complaint_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detected_category: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.9, nullable=False)
    urgency_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    severity: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    recommended_department: Mapped[str] = mapped_column(String(100), default="Public Works", nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # Structured JSON metadata
    extracted_entities: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    vision_analysis: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Provider audit info
    provider_used: Mapped[str] = mapped_column(String(50), default="mock", nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), default="rule-heuristic-v1", nullable=False)
    processing_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    complaint = relationship("Complaint", back_populates="ai_analysis")

    def __repr__(self) -> str:
        return f"<AIAnalysis complaint_id={self.complaint_id} cat={self.detected_category} conf={self.confidence_score}>"
