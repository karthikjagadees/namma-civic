"""Add incident priority, public timeline, delivery audit, and preferences.

Revision ID: 0004_incident_follow_up
Revises: 0003_duplicate_detection
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_incident_follow_up"
down_revision: Union[str, None] = "0003_duplicate_detection"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create follow-up records and backfill incident priority from work orders."""
    op.add_column("incidents", sa.Column("priority", sa.String(20), nullable=False, server_default="medium"))
    op.get_bind().execute(sa.text(
        "UPDATE incidents SET priority = COALESCE(" 
        "(SELECT priority FROM work_orders WHERE work_orders.incident_id = incidents.id "
        "ORDER BY created_at DESC LIMIT 1), 'medium')"
    ))
    op.create_table(
        "incident_timeline",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("event_key", sa.String(100), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_incident_timeline_incident_created", "incident_timeline", ["incident_id", "created_at"])
    op.create_index("uq_incident_timeline_event_key", "incident_timeline", ["event_key"], unique=True)
    op.create_table(
        "incident_notification_preferences",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_key", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("provider_delivery_id", sa.String(120)),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_notification_deliveries_incident_created", "notification_deliveries", ["incident_id", "created_at"])
    op.create_index(
        "uq_notification_delivery_event_channel", "notification_deliveries",
        ["incident_id", "recipient_user_id", "event_key", "channel"], unique=True,
    )


def downgrade() -> None:
    """Drop follow-up data and incident priority field."""
    op.drop_index("uq_notification_delivery_event_channel", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_incident_created", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_table("incident_notification_preferences")
    op.drop_index("uq_incident_timeline_event_key", table_name="incident_timeline")
    op.drop_index("ix_incident_timeline_incident_created", table_name="incident_timeline")
    op.drop_table("incident_timeline")
    op.drop_column("incidents", "priority")
