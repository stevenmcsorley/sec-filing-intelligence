"""Initial schema with companies, filings, organizations, subscriptions, and watchlists

Revision ID: 001
Revises:
Create Date: 2025-10-11 07:50:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
    # Companies table
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cik"),
    )
    op.create_index(op.f("ix_companies_cik"), "companies", ["cik"], unique=False)
    op.create_index(op.f("ix_companies_ticker"), "companies", ["ticker"], unique=False)

    # Filings table
    op.create_table(
        "filings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=True),
        sa.Column("form_type", sa.String(length=20), nullable=False),
        sa.Column("filed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accession_number", sa.String(length=20), nullable=False),
        sa.Column("source_urls", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("accession_number"),
    )
    op.create_index(op.f("ix_filings_cik"), "filings", ["cik"], unique=False)
    op.create_index(op.f("ix_filings_ticker"), "filings", ["ticker"], unique=False)
    op.create_index(op.f("ix_filings_form_type"), "filings", ["form_type"], unique=False)
    op.create_index(op.f("ix_filings_filed_at"), "filings", ["filed_at"], unique=False)
    op.create_index(
        op.f("ix_filings_accession_number"), "filings", ["accession_number"], unique=False
    )
    op.create_index(op.f("ix_filings_status"), "filings", ["status"], unique=False)

    # Filing blobs table
    op.create_table(
        "filing_blobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filing_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Filing sections table
    op.create_table(
        "filing_sections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filing_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_filing_sections_text_hash"), "filing_sections", ["text_hash"], unique=False
    )

    # Organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=False)

    # User organizations table (many-to-many with roles)
    op.create_table(
        "user_organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_organizations_user_id"), "user_organizations", ["user_id"], unique=False
    )

    # Subscriptions table
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False),
        sa.Column("features", sa.Text(), nullable=True),
        sa.Column("limits", sa.Text(), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id"),
    )

    # Watchlists table
    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_watchlists_user_id"), "watchlists", ["user_id"], unique=False)

    # Watchlist items table
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watchlist_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["watchlist_id"], ["watchlists.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("watchlist_id", "ticker", name="uq_watchlist_ticker"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("watchlist_items")
    op.drop_table("watchlists")
    op.drop_table("subscriptions")
    op.drop_table("user_organizations")
    op.drop_table("organizations")
    op.drop_table("filing_sections")
    op.drop_table("filing_blobs")
    op.drop_table("filings")
    op.drop_table("companies")
