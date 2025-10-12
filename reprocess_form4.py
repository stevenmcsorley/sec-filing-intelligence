#!/usr/bin/env python3
"""Script to re-process existing Form 4 filings for issuer extraction."""

import asyncio
import logging
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from app.models.filing import Filing, FilingBlob
from app.models.company import Company
from app.sec_utils import extract_issuer_cik
from app.services.ticker_lookup import TickerLookupService
from app.downloader.storage import MinioStorageBackend

# Set up logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


async def reprocess_form4_filings():
    """Re-process existing Form 4 filings to extract issuer information."""
    # Get database URL from environment
    db_url = os.getenv('DATABASE_URL', 'postgresql+asyncpg://postgres:postgres@db:5432/thestox')

    # Initialize MinIO storage backend
    storage = MinioStorageBackend(
        endpoint=os.getenv('MINIO_ENDPOINT', 'minio:9000'),
        access_key=os.getenv('MINIO_ACCESS_KEY', 'filings'),
        secret_key=os.getenv('MINIO_SECRET_KEY', 'filingsfilings'),
        bucket=os.getenv('MINIO_FILINGS_BUCKET', 'filings-raw'),
        secure=False,
    )

    engine = create_async_engine(db_url)

    async with AsyncSession(engine) as session:
        # Get all Form 4 filings that are parsed
        stmt = select(Filing.id, Filing.accession_number, Filing.cik, Filing.company_id, Filing.ticker).where(Filing.form_type == "4")
        result = await session.execute(stmt)
        filing_rows = result.all()

        LOGGER.info(f"Found {len(filing_rows)} Form 4 filings to re-process")

        for filing_row in filing_rows:
            filing_id, accession, filing_cik, company_id, ticker = filing_row
            LOGGER.info(f"Processing filing: {accession}")

            # Extract issuer CIK from raw filing content (XML)
            issuer_cik = None

            # First try the raw blob content
            blob_stmt = select(FilingBlob).where(FilingBlob.filing_id == filing_id, FilingBlob.kind == 'raw')
            raw_blob = (await session.execute(blob_stmt)).scalar_one_or_none()

            if raw_blob:
                try:
                    raw_content = await storage.fetch(raw_blob.location)
                    raw_text = raw_content.decode('utf-8', errors='ignore')
                    issuer_cik = extract_issuer_cik(raw_text)
                    if issuer_cik:
                        LOGGER.info(f"Extracted issuer CIK from raw content: {issuer_cik}")
                except Exception as e:
                    LOGGER.warning(f"Failed to fetch raw blob content for {accession}: {e}")

            if not issuer_cik:
                LOGGER.warning(f"Could not extract issuer CIK from filing {accession}")
                continue

            # If issuer CIK is different from filing CIK, update the company association
            if issuer_cik != filing_cik:
                # Check if issuer company already exists
                issuer_company_stmt = select(Company).where(Company.cik == issuer_cik)
                issuer_company = (await session.execute(issuer_company_stmt)).scalar_one_or_none()

                if issuer_company is None:
                    # Create new company for the issuer
                    ticker_service = TickerLookupService()
                    company_info = await ticker_service.get_company_info_for_cik(issuer_cik)

                    issuer_company = Company(
                        cik=issuer_cik,
                        name=company_info.get("company_name", f"Company {issuer_cik}") if company_info else f"Company {issuer_cik}",
                        ticker=company_info.get("ticker") if company_info else None
                    )
                    session.add(issuer_company)
                    await session.flush()

                    LOGGER.info(f"Created new issuer company: {issuer_company.name} ({issuer_cik})")
                else:
                    # Update existing issuer company info if needed
                    ticker_service = TickerLookupService()
                    company_info = await ticker_service.get_company_info_for_cik(issuer_cik)

                    if company_info:
                        if company_info.get("company_name") and issuer_company.name.startswith("Company "):
                            issuer_company.name = company_info["company_name"]
                        if company_info.get("ticker") and not issuer_company.ticker:
                            issuer_company.ticker = company_info["ticker"]

                    LOGGER.info(f"Updated existing issuer company: {issuer_company.name} ({issuer_cik})")

                # Update filing to point to the correct issuer company
                old_cik = filing_cik
                update_stmt = update(Filing).where(Filing.id == filing_id).values(
                    company_id=issuer_company.id,
                    cik=issuer_cik,
                    ticker=issuer_company.ticker
                )
                await session.execute(update_stmt)

                LOGGER.info(f"Updated filing {accession}: CIK {old_cik} -> {issuer_cik}")

            # Commit changes for this filing
            await session.commit()

        LOGGER.info("Re-processing complete")


if __name__ == "__main__":
    asyncio.run(reprocess_form4_filings())