"""
Namma Civic — Department Model
Defines civic departments responsible for handling complaints.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Department(Base):
    """
    Municipal / Civic Department (e.g. Roads, Sanitation, Water Works).
    """
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sla_hours_default: Mapped[int] = mapped_column(Integer, default=48, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

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

    @property
    def contact_email(self) -> Optional[str]:
        return self.email

    @property
    def head_name(self) -> Optional[str]:
        heads = {
            "ROADS": "Officer Sarah Chen (Chief of Pavements)",
            "WATER": "Officer Marcus Vance (Water Resources Dir.)",
            "SANITATION": "Officer Priya Sharma (Sanitation Superintendent)",
            "ELECTRICAL": "Officer David Kalu (Grid & Lighting Supv.)",
        }
        return heads.get(self.code, "Designated Chief Engineer")

    def __repr__(self) -> str:
        return f"<Department id={self.id} code={self.code} name={self.name}>"
