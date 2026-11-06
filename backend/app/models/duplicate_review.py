"""Officer review cases and durable labels for duplicate detection."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DuplicateReviewCase(Base):
    """One pending grey-zone review for a preserved complaint."""

    __tablename__ = "duplicate_review_cases"
    __table_args__ = (
        Index("uq_duplicate_review_case_complaint", "complaint_id", unique=True),
        Index("ix_duplicate_review_case_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    complaint_id: Mapped[str] = mapped_column(ForeignKey("complaints.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    failures: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    candidates: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    resolution_action: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    resolved_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DuplicateReviewDecision(Base):
    """Immutable officer decision and binary duplicate label for one candidate pair."""

    __tablename__ = "duplicate_review_decisions"
    __table_args__ = (
        Index("ix_duplicate_review_decision_case_created", "review_case_id", "created_at"),
        Index("ix_duplicate_review_decision_pair", "complaint_id", "candidate_incident_id", "officer_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    review_case_id: Mapped[str] = mapped_column(ForeignKey("duplicate_review_cases.id", ondelete="RESTRICT"), nullable=False)
    complaint_id: Mapped[str] = mapped_column(ForeignKey("complaints.id", ondelete="RESTRICT"), nullable=False)
    candidate_incident_id: Mapped[Optional[str]] = mapped_column(ForeignKey("incidents.id", ondelete="RESTRICT"), nullable=True)
    officer_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evidence: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
