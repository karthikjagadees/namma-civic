"""Persisted municipal work orders associated with civic incidents."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class WorkOrderStatus(str, PyEnum):
    """Lifecycle states used to determine whether an order is still active."""

    queued = "queued"
    assigned = "assigned"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class WorkOrder(Base):
    """A persisted unit of municipal work for one incident."""

    __tablename__ = "work_orders"
    __table_args__ = (
        Index(
            "uq_work_orders_one_active_per_incident",
            "incident_id",
            unique=True,
            sqlite_where=text("status NOT IN ('completed', 'cancelled')"),
            postgresql_where=text("status NOT IN ('completed', 'cancelled')"),
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    incident_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("incidents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    department_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
    status: Mapped[WorkOrderStatus] = mapped_column(
        Enum(WorkOrderStatus), nullable=False, default=WorkOrderStatus.queued
    )
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    assigned_crew: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    incident = relationship("Incident", back_populates="work_orders")

    def __repr__(self) -> str:
        return f"<WorkOrder id={self.id} incident={self.incident_id} status={self.status}>"
