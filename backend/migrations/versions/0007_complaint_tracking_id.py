"""Add citizen-facing unique tracking IDs to complaints.

Revision ID: 0007_complaint_tracking_id
Revises: 0006_phase7_hardening

Adds ``complaints.tracking_id`` (e.g. ``NC-7K4P-9XQ2``), back-fills every
existing complaint with a unique code, then enforces uniqueness with an index.

SQLite cannot ``ALTER COLUMN ... SET NOT NULL`` in place, so the final step uses
Alembic batch mode (as migration 0003 already does for ``complaints``).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core.tracking import generate_tracking_id


revision: str = "0007_complaint_tracking_id"
down_revision: Union[str, None] = "0006_phase7_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the column, back-fill unique codes for existing rows, add the index."""
    op.add_column("complaints", sa.Column("tracking_id", sa.String(16), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id FROM complaints ORDER BY created_at, id")).fetchall()
    used: set[str] = set()
    for (complaint_id,) in rows:
        code = generate_tracking_id()
        while code in used:
            code = generate_tracking_id()
        used.add(code)
        bind.execute(
            sa.text("UPDATE complaints SET tracking_id = :code WHERE id = :cid"),
            {"code": code, "cid": complaint_id},
        )

    # Batch mode (same approach as 0003) so SQLite can enforce NOT NULL by
    # rebuilding the table; other databases use a plain ALTER.
    with op.batch_alter_table("complaints") as batch_op:
        batch_op.alter_column("tracking_id", existing_type=sa.String(16), nullable=False)
        batch_op.create_index("ix_complaints_tracking_id", ["tracking_id"], unique=True)


def downgrade() -> None:
    """Remove tracking IDs (the internal UUID remains the primary key)."""
    with op.batch_alter_table("complaints") as batch_op:
        batch_op.drop_index("ix_complaints_tracking_id")
        batch_op.drop_column("tracking_id")
