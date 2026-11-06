"""Add incidents, versioned report links, work orders, and legacy backfill.

Revision ID: 0002_incidents
Revises: 0001_baseline
"""
from __future__ import annotations

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = "0002_incidents"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create incident tables, then give each existing complaint its own incident."""
    category = sa.Enum(
        "pothole", "garbage", "water_leakage", "street_light", "drainage",
        "traffic_signal", "encroachment", "other", name="complaintcategory",
    )
    incident_status = sa.Enum("open", "in_progress", "resolved", "closed", name="incidentstatus")
    decision_source = sa.Enum("auto", "officer", "backfill", name="reportlinkdecisionsource")
    work_order_status = sa.Enum(
        "queued", "assigned", "in_progress", "completed", "cancelled", name="workorderstatus"
    )

    op.create_table(
        "incidents",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category", category, nullable=False),
        sa.Column("status", incident_status, nullable=False),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("address", sa.String(500)),
        sa.Column("landmark", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_incidents_category", "incidents", ["category"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_latitude", "incidents", ["latitude"])
    op.create_index("ix_incidents_longitude", "incidents", ["longitude"])

    op.create_table(
        "report_links",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("complaint_id", sa.String(36), sa.ForeignKey("complaints.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("match_score", sa.Float()),
        sa.Column("signal_evidence", sa.JSON(), nullable=False),
        sa.Column("decision_source", decision_source, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("supersedes_link_id", sa.String(36), sa.ForeignKey("report_links.id", ondelete="RESTRICT")),
        sa.Column("decided_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decision_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "match_score IS NULL OR (match_score >= 0 AND match_score <= 1)",
            name="ck_report_links_match_score_range",
        ),
    )
    op.create_index("ix_report_links_complaint_id", "report_links", ["complaint_id"])
    op.create_index("ix_report_links_incident_id", "report_links", ["incident_id"])
    op.create_index(
        "uq_report_links_one_active_per_complaint",
        "report_links",
        ["complaint_id"],
        unique=True,
        sqlite_where=sa.text("is_active = 1"),
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "work_orders",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("department_id", sa.String(36), sa.ForeignKey("departments.id", ondelete="SET NULL")),
        sa.Column("external_id", sa.String(100), unique=True),
        sa.Column("status", work_order_status, nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("assigned_crew", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_work_orders_incident_id", "work_orders", ["incident_id"])
    op.create_index(
        "uq_work_orders_one_active_per_incident",
        "work_orders",
        ["incident_id"],
        unique=True,
        sqlite_where=sa.text("status NOT IN ('completed', 'cancelled')"),
        postgresql_where=sa.text("status NOT IN ('completed', 'cancelled')"),
    )

    bind = op.get_bind()
    complaints = sa.table(
        "complaints",
        sa.column("id", sa.String()),
        sa.column("title", sa.String()),
        sa.column("category", sa.String()),
        sa.column("status", sa.String()),
        sa.column("latitude", sa.Float()),
        sa.column("longitude", sa.Float()),
        sa.column("address", sa.String()),
        sa.column("landmark", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("resolved_at", sa.DateTime(timezone=True)),
    )
    incidents = sa.table(
        "incidents",
        sa.column("id", sa.String()),
        sa.column("title", sa.String()),
        sa.column("category", sa.String()),
        sa.column("status", sa.String()),
        sa.column("latitude", sa.Float()),
        sa.column("longitude", sa.Float()),
        sa.column("address", sa.String()),
        sa.column("landmark", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("resolved_at", sa.DateTime(timezone=True)),
    )
    report_links = sa.table(
        "report_links",
        sa.column("id", sa.String()),
        sa.column("complaint_id", sa.String()),
        sa.column("incident_id", sa.String()),
        sa.column("match_score", sa.Float()),
        sa.column("signal_evidence", sa.JSON()),
        sa.column("decision_source", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    rows = bind.execute(sa.select(complaints)).mappings().all()
    for complaint in rows:
        incident_id = str(uuid.uuid4())
        old_status = complaint["status"]
        mapped_status = (
            "resolved" if old_status == "resolved"
            else "closed" if old_status == "rejected"
            else "in_progress" if old_status in ("assigned", "in_progress")
            else "open"
        )
        incident_row = {
            "id": incident_id,
            "title": complaint["title"],
            "category": complaint["category"],
            "status": mapped_status,
            "latitude": complaint["latitude"],
            "longitude": complaint["longitude"],
            "address": complaint["address"],
            "landmark": complaint["landmark"],
            "created_at": complaint["created_at"],
            "updated_at": complaint["updated_at"],
            "resolved_at": complaint["resolved_at"] if mapped_status == "resolved" else None,
        }
        bind.execute(incidents.insert().values(**incident_row))
        bind.execute(
            report_links.insert().values(
                id=str(uuid.uuid4()),
                complaint_id=complaint["id"],
                incident_id=incident_id,
                match_score=None,
                signal_evidence={"source": "backfill", "reason": "Legacy report had no incident link."},
                decision_source="backfill",
                is_active=True,
                created_at=complaint["created_at"],
            )
        )


def downgrade() -> None:
    """Remove incident tables; downgrade discards incident/link/order data."""
    op.drop_index("uq_work_orders_one_active_per_incident", table_name="work_orders")
    op.drop_index("ix_work_orders_incident_id", table_name="work_orders")
    op.drop_table("work_orders")
    op.drop_index("uq_report_links_one_active_per_complaint", table_name="report_links")
    op.drop_index("ix_report_links_incident_id", table_name="report_links")
    op.drop_index("ix_report_links_complaint_id", table_name="report_links")
    op.drop_table("report_links")
    for name in ("longitude", "latitude", "status", "category"):
        op.drop_index(f"ix_incidents_{name}", table_name="incidents")
    op.drop_table("incidents")
    bind = op.get_bind()
    for enum_type in (
        sa.Enum("queued", "assigned", "in_progress", "completed", "cancelled", name="workorderstatus"),
        sa.Enum("auto", "officer", "backfill", name="reportlinkdecisionsource"),
        sa.Enum("open", "in_progress", "resolved", "closed", name="incidentstatus"),
    ):
        enum_type.drop(bind, checkfirst=True)
