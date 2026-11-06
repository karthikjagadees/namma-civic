"""Add complaint webhook idempotency key.

Revision ID: 0006_phase7_hardening
Revises: 0005_officer_duplicate_review
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_phase7_hardening"
down_revision: Union[str, None] = "0005_officer_duplicate_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Persist optional per-citizen replay keys with a uniqueness guarantee."""
    op.add_column("complaints", sa.Column("idempotency_key", sa.String(255), nullable=True))
    op.create_index(
        "uq_complaint_citizen_idempotency",
        "complaints",
        ["citizen_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    """Remove webhook replay protection data."""
    op.drop_index("uq_complaint_citizen_idempotency", table_name="complaints")
    op.drop_column("complaints", "idempotency_key")
