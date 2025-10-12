#!/usr/bin/env python3
"""Reprocess Form 144 and Schedule 13D/A filings to extract issuer CIK from content."""

import asyncio
import logging
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.filing import Filing
from app.models.company import Company
from app.sec_utils import extract_issuer_cik, extract_issuer_name
from app.services.ticker_lookup import TickerLookupService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def reprocess_other_forms() -> None:
    """Reprocess Form 144 and Schedule 13D/A filings to extract issuer information."""
    # Get database URL from environment
    db_url = os.getenv('DATABASE_URL', 'postgresql+asyncpg://filings:filings@postgres:5432/filings')

    engine = create_async_engine(db_url)

    async with AsyncSession(engine) as session:
        # Get all Form 144 and Schedule 13D/A filings
        stmt = select(Filing).where(Filing.form_type.in_(['144', 'SCHEDULE 13D/A'])).options(selectinload(Filing.sections))
        result = await session.execute(stmt)
        filings = result.scalars().all()

        logger.info(f"Found {len(filings)} Form 144/Schedule 13D/A filings to process")

        ticker_service = TickerLookupService()
        updated_count = 0

        for filing in filings:
            filing_id = filing.id
            accession = filing.accession_number
            form_type = filing.form_type
            logger.info(f"Processing filing {filing_id} ({form_type}) - {accession}")

            # Extract issuer CIK from filing content
            issuer_cik = None
            issuer_name = None

            if filing.sections:
                for section in filing.sections:
                    issuer_cik = extract_issuer_cik(section.content)
                    if issuer_cik:
                        issuer_name = extract_issuer_name(section.content)
                        logger.info(f"Extracted issuer CIK: {issuer_cik}, name: {issuer_name}")
                        break

            if not issuer_cik:
                logger.warning(f"No issuer CIK found for filing {filing_id}")
                continue

            # Get or create company record for the issuer
            company_stmt = select(Company).where(Company.cik == issuer_cik)
            result = await session.execute(company_stmt)
            company = result.scalar_one_or_none()

            if not company:
                # Create new company record
                company = Company(
                    cik=issuer_cik,
                    name=issuer_name or f"CIK: {issuer_cik}",
                    ticker=None
                )
                session.add(company)
                await session.flush()  # Get the ID
                logger.info(f"Created new company: {company.name} (CIK: {company.cik})")

            # Update filing to point to the issuer company
            old_company_id = filing.company_id
            company_id = company.id
            company_name = company.name  # Store name before commit
            filing.company_id = company_id
            filing.cik = issuer_cik  # Update the filing CIK to be the issuer CIK

            updated_count += 1
            logger.info(f"Updated filing {filing_id}: {old_company_id} -> {company_id} ({company_name})")

        # Commit all changes at once
        await session.commit()
        logger.info(f"Successfully updated {updated_count} filings")

        # Now update tickers for the companies we created/updated
        logger.info("Updating tickers for companies...")
        ticker_updates = 0
        for filing in filings:
            # Get the company for this filing
            company = filing.company
            if company and not company.ticker:
                try:
                    ticker = await ticker_service.get_ticker_for_cik(company.cik)
                    if ticker:
                        # Update in a separate transaction
                        async with AsyncSession(engine) as update_session:
                            # Load the company in this session and update it
                            company_to_update = await update_session.get(Company, company.id)
                            if company_to_update:
                                company_to_update.ticker = ticker
                                await update_session.commit()
                                logger.info(f"Set ticker {ticker} for company {company.name}")
                                ticker_updates += 1
                except Exception as e:
                    logger.warning(f"Failed to update ticker for {company.name}: {e}")

        logger.info(f"Updated tickers for {ticker_updates} companies")


async def main() -> None:
    """Main entry point."""
    await reprocess_other_forms()


if __name__ == "__main__":
    asyncio.run(main())