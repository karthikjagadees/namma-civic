"""Versioned associations between immutable citizen reports and incidents."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Dict, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReportLinkDecisionSource(str, PyEnum):
    """Who or what established a report-to-incident link."""

    auto = "auto"
    officer = "officer"
    backfill = "backfill"


class ReportLink(Base):
    """One version of a complaint's association with an incident.

    Superseded rows remain as history. Exactly one row per complaint may be
    active; backfill and the application transaction ensure at least one.
    """

    __tablename__ = "report_links"
    __table_args__ = (
        CheckConstraint(
            "match_score IS NULL OR (match_score >= 0 AND match_score <= 1)",
            name="ck_report_links_match_score_range",
        ),
        Index(
            "uq_report_links_one_active_per_complaint",
            "complaint_id",
            unique=True,
            sqlite_where=text("is_active = 1"),
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    complaint_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("complaints.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    incident_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("incidents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    signal_evidence: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    decision_source: Mapped[ReportLinkDecisionSource] = mapped_column(
        Enum(ReportLinkDecisionSource), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    supersedes_link_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("report_links.id", ondelete="RESTRICT"), nullable=True
    )
    decided_by_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    complaint = relationship("Complaint", back_populates="report_links")
    incident = relationship("Incident", back_populates="report_links")
    supersedes = relationship("ReportLink", remote_side="ReportLink.id", uselist=False)

    def __repr__(self) -> str:
        return f"<ReportLink id={self.id} complaint={self.complaint_id} incident={self.incident_id}>"
