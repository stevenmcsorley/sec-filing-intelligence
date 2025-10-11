"""Add filing_entities table for entity extraction results."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "filing_entities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filing_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("analysis_id", sa.Integer(), nullable=True),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        sa.Column("attributes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["analysis_id"], ["filing_analyses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["filing_sections.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_filing_entities_filing_id",
        "filing_entities",
        ["filing_id"],
        unique=False,
    )
    op.create_index(
        "ix_filing_entities_section_id",
        "filing_entities",
        ["section_id"],
        unique=False,
    )
    op.create_index(
        "ix_filing_entities_analysis_id",
        "filing_entities",
        ["analysis_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_filing_entities_analysis_id", table_name="filing_entities")
    op.drop_index("ix_filing_entities_section_id", table_name="filing_entities")
    op.drop_index("ix_filing_entities_filing_id", table_name="filing_entities")
    op.drop_table("filing_entities")
