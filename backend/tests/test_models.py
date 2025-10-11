"""Integration tests for SQLAlchemy models and database operations."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.models import (
    Company,
    Filing,
    FilingAnalysis,
    FilingBlob,
    FilingEntity,
    FilingSection,
    Organization,
    Subscription,
    UserOrganization,
    Watchlist,
    WatchlistItem,
)
from app.models.analysis import AnalysisType
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


@pytest.mark.asyncio
async def test_filing_analysis_links_section(db_session: AsyncSession) -> None:
    """Ensure analyses can be persisted for a filing section."""
    company = Company(cik="0009876543", name="Example Analytics Corp")
    db_session.add(company)
    await db_session.flush()

    filing = Filing(
        company_id=company.id,
        cik=company.cik,
        form_type="10-Q",
        filed_at=datetime.now(UTC),
        accession_number="0009876543-25-000010",
        source_urls='["https://example.com/q"]',
        status="parsed",
    )
    db_session.add(filing)
    await db_session.flush()

    section = FilingSection(
        filing_id=filing.id,
        title="Management Discussion",
        ordinal=1,
        content="Detailed discussion of quarterly performance.",
    )
    db_session.add(section)
    await db_session.flush()

    analysis = FilingAnalysis(
        job_id="0009876543-25-000010:1:0",
        filing_id=filing.id,
        section_id=section.id,
        chunk_index=0,
        analysis_type="section_chunk_summary",
        model="mixtral-8x7b-32768",
        content="- Strong revenue growth noted.",
        prompt_tokens=500,
        completion_tokens=120,
        total_tokens=620,
    )
    db_session.add(analysis)
    await db_session.commit()

    result = await db_session.execute(
        select(Filing)
        .where(Filing.id == filing.id)
        .options(selectinload(Filing.analyses), selectinload(Filing.sections))
    )
    loaded = result.scalar_one()
    assert len(loaded.analyses) == 1
    assert loaded.analyses[0].section_id == section.id


@pytest.mark.asyncio
async def test_filing_entity_relationships(db_session: AsyncSession) -> None:
    """Ensure entity extraction results persist with relationships."""
    company = Company(cik="0007777777", name="Entity Corp")
    db_session.add(company)
    await db_session.flush()

    filing = Filing(
        company_id=company.id,
        cik=company.cik,
        form_type="8-K",
        filed_at=datetime.now(UTC),
        accession_number="0007777777-25-000123",
        source_urls='["https://example.com"]',
        status="analyzed",
    )
    db_session.add(filing)
    await db_session.flush()

    section = FilingSection(
        filing_id=filing.id,
        title="Executive Changes",
        ordinal=1,
        content="Executive news",
    )
    db_session.add(section)
    await db_session.flush()

    analysis = FilingAnalysis(
        job_id="0007777777-25-000123:1:0:entity",
        filing_id=filing.id,
        section_id=section.id,
        chunk_index=None,
        analysis_type=AnalysisType.ENTITY_EXTRACTION.value,
        model="test-model",
        content="[]",
    )
    db_session.add(analysis)
    await db_session.flush()

    entity = FilingEntity(
        filing_id=filing.id,
        section_id=section.id,
        analysis_id=analysis.id,
        entity_type="executive_change",
        label="CFO resigned",
        confidence=0.9,
        source_excerpt="CFO resigned",
        attributes='{"effective_date":"2025-03-01"}',
    )
    db_session.add(entity)
    await db_session.commit()

    result = await db_session.execute(
        select(FilingEntity).where(FilingEntity.analysis_id == analysis.id)
    )
    stored = result.scalar_one()
    assert stored.filing_id == filing.id
    assert stored.analysis is not None
    assert stored.section is not None
