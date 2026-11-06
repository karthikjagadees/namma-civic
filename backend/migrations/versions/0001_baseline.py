"""Baseline for the existing Namma Civic schema before incident modeling.

Revision ID: 0001_baseline
Revises: None
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the six tables present before incident support was added."""
    user_role = sa.Enum("citizen", "officer", "admin", name="userrole")
    category = sa.Enum(
        "pothole", "garbage", "water_leakage", "street_light", "drainage",
        "traffic_signal", "encroachment", "other", name="complaintcategory",
    )
    complaint_status = sa.Enum(
        "pending", "analyzing", "verified", "assigned", "in_progress",
        "resolved", "rejected", name="complaintstatus",
    )
    priority = sa.Enum("low", "medium", "high", "critical", name="prioritylevel")
    source = sa.Enum("web", "mobile", "voice", "whatsapp", name="complaintsource")
    media_type = sa.Enum("image", "audio", "video", "document", name="mediatype")

    op.create_table(
        "departments",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(20)),
        sa.Column("sla_hours_default", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_departments_code", "departments", ["code"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20)),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("department_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "complaints",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("citizen_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", category, nullable=False),
        sa.Column("status", complaint_status, nullable=False),
        sa.Column("priority", priority, nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("address", sa.String(500)),
        sa.Column("landmark", sa.String(255)),
        sa.Column("department_id", sa.String(36), sa.ForeignKey("departments.id", ondelete="SET NULL")),
        sa.Column("assigned_officer_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("source", source, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    for column in (
        "citizen_id", "category", "status", "priority", "latitude", "longitude",
        "department_id", "assigned_officer_id",
    ):
        op.create_index(f"ix_complaints_{column}", "complaints", [column])

    op.create_table(
        "complaint_media",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("complaint_id", sa.String(36), sa.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_type", media_type, nullable=False),
        sa.Column("file_url", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("caption", sa.String(255)),
        sa.Column("is_resolution_evidence", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_complaint_media_complaint_id", "complaint_media", ["complaint_id"])

    op.create_table(
        "complaint_timeline",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("complaint_id", sa.String(36), sa.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", complaint_status, nullable=False),
        sa.Column("changed_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_complaint_timeline_complaint_id", "complaint_timeline", ["complaint_id"])

    op.create_table(
        "ai_analyses",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("complaint_id", sa.String(36), sa.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("detected_category", sa.String(50), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("urgency_score", sa.Float(), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False),
        sa.Column("recommended_department", sa.String(100), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("extracted_entities", sa.JSON(), nullable=False),
        sa.Column("vision_analysis", sa.JSON()),
        sa.Column("provider_used", sa.String(50), nullable=False),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("processing_time_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_analyses_complaint_id", "ai_analyses", ["complaint_id"], unique=True)


def downgrade() -> None:
    """Drop the pre-incident schema in reverse dependency order."""
    op.drop_index("ix_ai_analyses_complaint_id", table_name="ai_analyses")
    op.drop_table("ai_analyses")
    op.drop_index("ix_complaint_timeline_complaint_id", table_name="complaint_timeline")
    op.drop_table("complaint_timeline")
    op.drop_index("ix_complaint_media_complaint_id", table_name="complaint_media")
    op.drop_table("complaint_media")
    for column in (
        "assigned_officer_id", "department_id", "longitude", "latitude",
        "priority", "status", "category", "citizen_id",
    ):
        op.drop_index(f"ix_complaints_{column}", table_name="complaints")
    op.drop_table("complaints")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_departments_code", table_name="departments")
    op.drop_table("departments")
    bind = op.get_bind()
    for enum_type in (
        sa.Enum("image", "audio", "video", "document", name="mediatype"),
        sa.Enum("web", "mobile", "voice", "whatsapp", name="complaintsource"),
        sa.Enum("low", "medium", "high", "critical", name="prioritylevel"),
        sa.Enum("pending", "analyzing", "verified", "assigned", "in_progress", "resolved", "rejected", name="complaintstatus"),
        sa.Enum("pothole", "garbage", "water_leakage", "street_light", "drainage", "traffic_signal", "encroachment", "other", name="complaintcategory"),
        sa.Enum("citizen", "officer", "admin", name="userrole"),
    ):
        enum_type.drop(bind, checkfirst=True)
