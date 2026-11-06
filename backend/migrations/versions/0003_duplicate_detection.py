"""Persist photo perceptual hashes and link recurrence incidents.

Revision ID: 0003_duplicate_detection
Revises: 0002_incidents
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core.config import get_upload_directory
from app.deduplication.images import compute_phash_for_url


revision: str = "0003_duplicate_detection"
down_revision: Union[str, None] = "0002_incidents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def backfill_media_hashes(connection, upload_directory: str | Path) -> int:
    """Hash accessible legacy image files and leave absent/unreadable files null."""
    media = sa.table(
        "complaint_media",
        sa.column("id", sa.String()),
        sa.column("file_url", sa.String()),
        sa.column("media_type", sa.String()),
        sa.column("perceptual_hash", sa.String()),
    )
    rows = connection.execute(
        sa.select(media.c.id, media.c.file_url).where(
            sa.func.lower(media.c.media_type) == "image",
            media.c.perceptual_hash.is_(None),
        )
    ).mappings()
    updated = 0
    for row in rows:
        image_hash = compute_phash_for_url(row["file_url"], upload_directory)
        if image_hash is not None:
            connection.execute(
                media.update().where(media.c.id == row["id"]).values(perceptual_hash=image_hash)
            )
            updated += 1
    return updated


def upgrade() -> None:
    """Add image hashes, uncertainty and recurrence fields, then backfill images."""
    op.add_column("complaint_media", sa.Column("perceptual_hash", sa.String(16), nullable=True))
    with op.batch_alter_table("complaints") as batch_op:
        batch_op.add_column(sa.Column("location_confidence", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("location_accuracy_m", sa.Float(), nullable=True))
        batch_op.create_check_constraint(
            "ck_complaints_location_confidence_range",
            "location_confidence IS NULL OR (location_confidence >= 0 AND location_confidence <= 1)",
        )
        batch_op.create_check_constraint(
            "ck_complaints_location_accuracy_nonnegative",
            "location_accuracy_m IS NULL OR location_accuracy_m >= 0",
        )
    with op.batch_alter_table("incidents") as batch_op:
        batch_op.add_column(sa.Column("location_confidence", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("location_accuracy_m", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "recurrence_of_incident_id",
                sa.String(36),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            "fk_incidents_recurrence_of_incident_id",
            "incidents",
            ["recurrence_of_incident_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_check_constraint(
            "ck_incidents_location_confidence_range",
            "location_confidence IS NULL OR (location_confidence >= 0 AND location_confidence <= 1)",
        )
        batch_op.create_check_constraint(
            "ck_incidents_location_accuracy_nonnegative",
            "location_accuracy_m IS NULL OR location_accuracy_m >= 0",
        )
    op.create_index(
        "ix_incidents_recurrence_of_incident_id",
        "incidents",
        ["recurrence_of_incident_id"],
    )
    backfill_media_hashes(op.get_bind(), get_upload_directory())


def downgrade() -> None:
    """Drop derived image hashes, location uncertainty and recurrence pointers."""
    op.drop_index("ix_incidents_recurrence_of_incident_id", table_name="incidents")
    with op.batch_alter_table("incidents") as batch_op:
        batch_op.drop_constraint("fk_incidents_recurrence_of_incident_id", type_="foreignkey")
        batch_op.drop_constraint("ck_incidents_location_confidence_range", type_="check")
        batch_op.drop_constraint("ck_incidents_location_accuracy_nonnegative", type_="check")
        batch_op.drop_column("recurrence_of_incident_id")
        batch_op.drop_column("location_accuracy_m")
        batch_op.drop_column("location_confidence")
    with op.batch_alter_table("complaints") as batch_op:
        batch_op.drop_constraint("ck_complaints_location_confidence_range", type_="check")
        batch_op.drop_constraint("ck_complaints_location_accuracy_nonnegative", type_="check")
        batch_op.drop_column("location_accuracy_m")
        batch_op.drop_column("location_confidence")
    op.drop_column("complaint_media", "perceptual_hash")
