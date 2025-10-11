"""Add downloaded_at and blob metadata columns"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "filings",
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "filing_blobs",
        sa.Column("checksum", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_filing_blobs_checksum", "filing_blobs", ["checksum"], unique=False)
    op.add_column(
        "filing_blobs",
        sa.Column("content_type", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("filing_blobs", "content_type")
    op.drop_index("ix_filing_blobs_checksum", table_name="filing_blobs")
    op.drop_column("filing_blobs", "checksum")
    op.drop_column("filings", "downloaded_at")
