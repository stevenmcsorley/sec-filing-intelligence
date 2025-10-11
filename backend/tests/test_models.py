"""Integration tests for SQLAlchemy models and database operations."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.models import (
    Company,
    Filing,
    FilingBlob,
    Organization,
    Subscription,
    UserOrganization,
    Watchlist,
    WatchlistItem,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


@pytest.mark.asyncio
async def test_create_company(db_session: AsyncSession) -> None:
    """Test creating a company."""
    company = Company(
        cik="0001234567",
        ticker="AAPL",
        name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics",
    )
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    assert company.id is not None
    assert company.cik == "0001234567"
    assert company.ticker == "AAPL"
    assert company.name == "Apple Inc."


@pytest.mark.asyncio
async def test_create_filing_with_company(db_session: AsyncSession) -> None:
    """Test creating a filing linked to a company."""
    company = Company(cik="0001234567", ticker="AAPL", name="Apple Inc.")
    db_session.add(company)
    await db_session.flush()

    filing = Filing(
        company_id=company.id,
        cik=company.cik,
        ticker=company.ticker,
        form_type="10-K",
        filed_at=datetime.now(UTC),
        accession_number="0001234567-23-000001",
        source_urls='["https://www.sec.gov/Archives/..."]',
        status="pending",
    )
    db_session.add(filing)
    await db_session.commit()
    await db_session.refresh(filing)

    assert filing.id is not None
    assert filing.company_id == company.id
    assert filing.form_type == "10-K"
    assert filing.accession_number == "0001234567-23-000001"


@pytest.mark.asyncio
async def test_filing_with_blobs(db_session: AsyncSession) -> None:
    """Test creating a filing with associated blobs."""
    company = Company(cik="0001234567", name="Test Corp")
    db_session.add(company)
    await db_session.flush()

    filing = Filing(
        company_id=company.id,
        cik=company.cik,
        form_type="8-K",
        filed_at=datetime.now(UTC),
        accession_number="0001234567-23-000002",
        source_urls='["https://example.com"]',
        status="downloaded",
    )
    db_session.add(filing)
    await db_session.flush()

    blob_raw = FilingBlob(
        filing_id=filing.id, kind="raw", location="s3://bucket/raw/file.html"
    )
    blob_text = FilingBlob(
        filing_id=filing.id, kind="text", location="s3://bucket/text/file.txt"
    )
    db_session.add_all([blob_raw, blob_text])
    await db_session.commit()

    # Query back with eager loading
    result = await db_session.execute(
        select(Filing).where(Filing.id == filing.id).options(selectinload(Filing.blobs))
    )
    filing_loaded = result.scalar_one()
    assert len(filing_loaded.blobs) == 2
    assert {b.kind for b in filing_loaded.blobs} == {"raw", "text"}


@pytest.mark.asyncio
async def test_organization_with_subscription(db_session: AsyncSession) -> None:
    """Test creating an organization with a subscription."""
    org = Organization(
        name="Test Org", slug="test-org", created_at=datetime.now(UTC)
    )
    db_session.add(org)
    await db_session.flush()

    subscription = Subscription(
        organization_id=org.id,
        tier="pro",
        features='{"real_time_alerts": true}',
        limits='{"max_tickers": 200}',
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(subscription)
    await db_session.commit()

    # Query back with eager loading
    result = await db_session.execute(
        select(Organization)
        .where(Organization.slug == "test-org")
        .options(selectinload(Organization.subscription))
    )
    org_loaded = result.scalar_one()
    assert org_loaded.subscription is not None
    assert org_loaded.subscription.tier == "pro"


@pytest.mark.asyncio
async def test_user_organization_membership(db_session: AsyncSession) -> None:
    """Test user-organization membership with roles."""
    org = Organization(
        name="Test Org", slug="test-org-2", created_at=datetime.now(UTC)
    )
    db_session.add(org)
    await db_session.flush()

    user_org = UserOrganization(
        user_id="keycloak-user-123",
        organization_id=org.id,
        role="org_admin",
        joined_at=datetime.now(UTC),
    )
    db_session.add(user_org)
    await db_session.commit()

    # Query back
    result = await db_session.execute(
        select(UserOrganization).where(UserOrganization.user_id == "keycloak-user-123")
    )
    membership = result.scalar_one()
    assert membership.role == "org_admin"
    assert membership.organization.slug == "test-org-2"


@pytest.mark.asyncio
async def test_watchlist_with_items(db_session: AsyncSession) -> None:
    """Test creating a watchlist with ticker items."""
    org = Organization(
        name="Test Org", slug="test-org-3", created_at=datetime.now(UTC)
    )
    db_session.add(org)
    await db_session.flush()

    watchlist = Watchlist(
        organization_id=org.id,
        user_id="keycloak-user-456",
        name="My Tech Stocks",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(watchlist)
    await db_session.flush()

    items = [
        WatchlistItem(
            watchlist_id=watchlist.id, ticker="AAPL", added_at=datetime.now(UTC)
        ),
        WatchlistItem(
            watchlist_id=watchlist.id, ticker="MSFT", added_at=datetime.now(UTC)
        ),
        WatchlistItem(
            watchlist_id=watchlist.id, ticker="GOOGL", added_at=datetime.now(UTC)
        ),
    ]
    db_session.add_all(items)
    await db_session.commit()

    # Query back with eager loading
    result = await db_session.execute(
        select(Watchlist)
        .where(Watchlist.id == watchlist.id)
        .options(selectinload(Watchlist.items))
    )
    watchlist_loaded = result.scalar_one()
    assert len(watchlist_loaded.items) == 3
    assert {item.ticker for item in watchlist_loaded.items} == {"AAPL", "MSFT", "GOOGL"}


@pytest.mark.asyncio
async def test_unique_constraints(db_session: AsyncSession) -> None:
    """Test that unique constraints are enforced."""
    from sqlalchemy.exc import IntegrityError

    company1 = Company(cik="0001111111", name="Company A")
    db_session.add(company1)
    await db_session.commit()

    # Try to create another company with same CIK
    company2 = Company(cik="0001111111", name="Company B")
    db_session.add(company2)

    with pytest.raises(IntegrityError):
        await db_session.flush()  # Use flush instead of commit to trigger the error
