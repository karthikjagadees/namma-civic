"""Incident models for grouping preserved citizen complaints by real issue."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import CheckConstraint, DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.complaint import ComplaintCategory


class IncidentStatus(str, PyEnum):
    """Operational state of the real-world civic issue."""

    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class Incident(Base):
    """A real-world civic issue that can be supported by many reports."""

    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(
            "location_confidence IS NULL OR (location_confidence >= 0 AND location_confidence <= 1)",
            name="ck_incidents_location_confidence_range",
        ),
        CheckConstraint(
            "location_accuracy_m IS NULL OR location_accuracy_m >= 0",
            name="ck_incidents_location_accuracy_nonnegative",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[ComplaintCategory] = mapped_column(
        Enum(ComplaintCategory), nullable=False, index=True
    )
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus), nullable=False, default=IncidentStatus.open, index=True
    )
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", server_default="medium")

    # These coordinates describe the incident's current display location. The
    # original report locations remain unchanged on Complaint rows.
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    landmark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_accuracy_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    recurrence_of_incident_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("incidents.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    recurrence_of = relationship("Incident", remote_side="Incident.id", uselist=False)
    report_links: Mapped[List["ReportLink"]] = relationship(
        "ReportLink", back_populates="incident", lazy="selectin"
    )
    work_orders: Mapped[List["WorkOrder"]] = relationship(
        "WorkOrder", back_populates="incident", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Incident id={self.id} title={self.title[:30]} status={self.status}>"
