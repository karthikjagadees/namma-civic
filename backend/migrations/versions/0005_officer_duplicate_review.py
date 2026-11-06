"""Persist officer duplicate-review cases, decisions, and labels.

Revision ID: 0005_officer_duplicate_review
Revises: 0004_incident_follow_up
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_officer_duplicate_review"
down_revision: Union[str, None] = "0004_incident_follow_up"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create durable grey-zone review queue and officer label tables."""
    op.create_table(
        "duplicate_review_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("complaint_id", sa.String(36), sa.ForeignKey("complaints.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("failures", sa.JSON(), nullable=False),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("resolution_action", sa.String(30)),
        sa.Column("resolved_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("uq_duplicate_review_case_complaint", "duplicate_review_cases", ["complaint_id"], unique=True)
    op.create_index("ix_duplicate_review_case_status_created", "duplicate_review_cases", ["status", "created_at"])
    op.create_table(
        "duplicate_review_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_case_id", sa.String(36), sa.ForeignKey("duplicate_review_cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("complaint_id", sa.String(36), sa.ForeignKey("complaints.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("candidate_incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="RESTRICT")),
        sa.Column("officer_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Float()),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_duplicate_review_decision_case_created", "duplicate_review_decisions", ["review_case_id", "created_at"])
    op.create_index("ix_duplicate_review_decision_pair", "duplicate_review_decisions", ["complaint_id", "candidate_incident_id", "officer_id"])


def downgrade() -> None:
    """Remove officer review case and label tables."""
    op.drop_index("ix_duplicate_review_decision_pair", table_name="duplicate_review_decisions")
    op.drop_index("ix_duplicate_review_decision_case_created", table_name="duplicate_review_decisions")
    op.drop_table("duplicate_review_decisions")
    op.drop_index("ix_duplicate_review_case_status_created", table_name="duplicate_review_cases")
    op.drop_index("uq_duplicate_review_case_complaint", table_name="duplicate_review_cases")
    op.drop_table("duplicate_review_cases")
