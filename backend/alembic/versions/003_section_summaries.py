"""Add filing analyses table for section summaries."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "filing_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("filing_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.Column("analysis_type", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("extra", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["filing_sections.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index(
        "ix_filing_analyses_filing_id", "filing_analyses", ["filing_id"], unique=False
    )
    op.create_index(
        "ix_filing_analyses_section_id", "filing_analyses", ["section_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_filing_analyses_section_id", table_name="filing_analyses")
    op.drop_index("ix_filing_analyses_filing_id", table_name="filing_analyses")
    op.drop_table("filing_analyses")
