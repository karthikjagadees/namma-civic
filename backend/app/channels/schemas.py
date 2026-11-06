"""Canonical, channel-independent representation of an incoming report."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.complaint import ComplaintSource


class CanonicalReport(BaseModel):
    """Normalized report data while preserving the citizen's original wording."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    address: Optional[str] = None
    landmark: Optional[str] = None
    photos: List[str] = Field(default_factory=list)
    language: Optional[str] = None
    reporter_id: Optional[str] = None
    reporter_contact: Optional[str] = None
    channel: ComplaintSource
    reported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    location_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    location_accuracy_m: Optional[float] = Field(default=None, ge=0.0)
    normalization_warnings: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def coordinates_are_a_pair(self) -> "CanonicalReport":
        """Reject half coordinates so downstream code cannot treat them as a point."""
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self
