"""Repository for filing-related database operations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.filing import Filing


class FilingRepository:
    """Repository for filing-related database operations."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.db_session = db_session

    async def list_filings(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        cik: str | None = None,
        ticker: str | None = None,
        form_type: str | None = None,
        status: str | None = None,
        filed_after: datetime | None = None,
        filed_before: datetime | None = None,
        order_by: str = "filed_at",
        order_desc: bool = True,
    ) -> list[Filing]:
        """List filings with optional filters and pagination.

        Args:
            limit: Maximum number of filings to return
            offset: Number of filings to skip
            cik: Filter by CIK
            ticker: Filter by ticker symbol
            form_type: Filter by form type (e.g., '10-K', '8-K')
            status: Filter by processing status
            filed_after: Filter filings filed after this datetime
            filed_before: Filter filings filed before this datetime
            order_by: Field to order by ('filed_at', 'id', etc.)
            order_desc: Order descending if True

        Returns:
            List of Filing objects
        """
        stmt = select(Filing).options(
            selectinload(Filing.company),
            selectinload(Filing.blobs),
            selectinload(Filing.sections),
        )

        # Apply filters
        if cik is not None:
            stmt = stmt.where(Filing.cik == cik)
        if ticker is not None:
            stmt = stmt.where(Filing.ticker == ticker)
        if form_type is not None:
            stmt = stmt.where(Filing.form_type == form_type)
        if status is not None:
            stmt = stmt.where(Filing.status == status)
        if filed_after is not None:
            stmt = stmt.where(Filing.filed_at >= filed_after)
        if filed_before is not None:
            stmt = stmt.where(Filing.filed_at <= filed_before)

        # Apply ordering
        order_column = getattr(Filing, order_by, Filing.filed_at)
        if order_desc:
            stmt = stmt.order_by(desc(order_column))
        else:
            stmt = stmt.order_by(order_column)

        # Apply pagination
        stmt = stmt.limit(limit).offset(offset)

        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_filing_by_id(self, filing_id: int) -> Filing | None:
        """Get a filing by its ID with related data.

        Args:
            filing_id: The filing ID

        Returns:
            Filing object or None if not found
        """
        stmt = (
            select(Filing)
            .where(Filing.id == filing_id)
            .options(
                selectinload(Filing.company),
                selectinload(Filing.blobs),
                selectinload(Filing.sections),
                selectinload(Filing.analyses),
                selectinload(Filing.entities),
            )
        )

        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_filing_by_accession(self, accession_number: str) -> Filing | None:
        """Get a filing by its accession number.

        Args:
            accession_number: The SEC accession number

        Returns:
            Filing object or None if not found
        """
        stmt = (
            select(Filing)
            .where(Filing.accession_number == accession_number)
            .options(
                selectinload(Filing.company),
                selectinload(Filing.blobs),
                selectinload(Filing.sections),
            )
        )

        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_filings(
        self,
        *,
        cik: str | None = None,
        ticker: str | None = None,
        form_type: str | None = None,
        status: str | None = None,
        filed_after: datetime | None = None,
        filed_before: datetime | None = None,
    ) -> int:
        """Count filings matching the given filters.

        Args:
            cik: Filter by CIK
            ticker: Filter by ticker symbol
            form_type: Filter by form type
            status: Filter by processing status
            filed_after: Filter filings filed after this datetime
            filed_before: Filter filings filed before this datetime

        Returns:
            Count of matching filings
        """
        stmt = select(Filing)

        # Apply filters
        if cik is not None:
            stmt = stmt.where(Filing.cik == cik)
        if ticker is not None:
            stmt = stmt.where(Filing.ticker == ticker)
        if form_type is not None:
            stmt = stmt.where(Filing.form_type == form_type)
        if status is not None:
            stmt = stmt.where(Filing.status == status)
        if filed_after is not None:
            stmt = stmt.where(Filing.filed_at >= filed_after)
        if filed_before is not None:
            stmt = stmt.where(Filing.filed_at <= filed_before)

        # Count query
        count_stmt = select(func.count()).select_from(stmt.subquery())
        result = await self.db_session.execute(count_stmt)
        return result.scalar_one()