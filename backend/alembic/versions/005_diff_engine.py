"""Create diff tables for filing comparison engine."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "filing_diffs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("current_filing_id", sa.Integer(), nullable=False),
        sa.Column("previous_filing_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("expected_sections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_sections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["current_filing_id"], ["filings.id"]),
        sa.ForeignKeyConstraint(["previous_filing_id"], ["filings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("current_filing_id"),
    )
    op.create_index("ix_filing_diffs_status", "filing_diffs", ["status"], unique=False)

    op.create_table(
        "filing_section_diffs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filing_diff_id", sa.Integer(), nullable=False),
        sa.Column("current_section_id", sa.Integer(), nullable=True),
        sa.Column("previous_section_id", sa.Integer(), nullable=True),
        sa.Column("analysis_id", sa.Integer(), nullable=True),
        sa.Column("section_ordinal", sa.Integer(), nullable=False),
        sa.Column("section_title", sa.String(length=255), nullable=False),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("impact", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["analysis_id"], ["filing_analyses.id"]),
        sa.ForeignKeyConstraint(["current_section_id"], ["filing_sections.id"]),
        sa.ForeignKeyConstraint(["filing_diff_id"], ["filing_diffs.id"]),
        sa.ForeignKeyConstraint(["previous_section_id"], ["filing_sections.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_filing_section_diffs_filing_diff_id",
        "filing_section_diffs",
        ["filing_diff_id"],
        unique=False,
    )
    op.create_index(
        "ix_filing_section_diffs_current_section_id",
        "filing_section_diffs",
        ["current_section_id"],
        unique=False,
    )
    op.create_index(
        "ix_filing_section_diffs_previous_section_id",
        "filing_section_diffs",
        ["previous_section_id"],
        unique=False,
    )
    op.create_index(
        "ix_filing_section_diffs_analysis_id",
        "filing_section_diffs",
        ["analysis_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_filing_section_diffs_analysis_id", table_name="filing_section_diffs")
    op.drop_index(
        "ix_filing_section_diffs_previous_section_id", table_name="filing_section_diffs"
    )
    op.drop_index(
        "ix_filing_section_diffs_current_section_id", table_name="filing_section_diffs"
    )
    op.drop_index("ix_filing_section_diffs_filing_diff_id", table_name="filing_section_diffs")
    op.drop_table("filing_section_diffs")
    op.drop_index("ix_filing_diffs_status", table_name="filing_diffs")
    op.drop_table("filing_diffs")
