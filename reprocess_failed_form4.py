#!/usr/bin/env python3
"""Reprocess failed Form 4 filings to extract issuer CIK information."""

import asyncio
import logging
from sqlalchemy import select

from app.config import get_settings
from app.db import create_async_engine, async_sessionmaker
from app.models.filing import Filing, FilingBlob, FilingStatus
from app.sec_utils import extract_issuer_cik
from app.services.ticker_lookup import TickerLookupService
from app.downloader.storage import MinioStorageBackend

LOGGER = logging.getLogger(__name__)


async def reprocess_failed_form4_filings():
    """Reprocess failed Form 4 filings to extract issuer CIK information."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    storage = MinioStorageBackend(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_filings_bucket,
        secure=settings.minio_secure,
        region=settings.minio_region,
    )

    async with async_sessionmaker(engine)() as session:
        # Get all failed Form 4 filings
        stmt = select(Filing).where(
            Filing.form_type == "4",
            Filing.status == FilingStatus.FAILED.value
        )
        result = await session.execute(stmt)
        failed_filings = result.scalars().all()

        LOGGER.info(f"Found {len(failed_filings)} failed Form 4 filings to reprocess")

        for filing in failed_filings:
            LOGGER.info(f"Reprocessing failed filing: {filing.accession_number}")

            # Extract issuer CIK from raw filing content (XML)
            issuer_cik = None

            # Try the raw blob content
            blob_stmt = select(FilingBlob).where(
                FilingBlob.filing_id == filing.id,
                FilingBlob.kind == 'raw'
            )
            raw_blob = (await session.execute(blob_stmt)).scalar_one_or_none()

            if raw_blob:
                try:
                    raw_content = await storage.fetch(raw_blob.location)
                    raw_text = raw_content.decode('utf-8', errors='ignore')
                    issuer_cik = extract_issuer_cik(raw_text)
                    if issuer_cik:
                        LOGGER.info(f"Extracted issuer CIK from raw content: {issuer_cik}")
                except Exception as e:
                    LOGGER.warning(f"Failed to fetch raw blob content for {filing.accession_number}: {e}")

            if not issuer_cik:
                LOGGER.warning(f"Could not extract issuer CIK from failed filing {filing.accession_number}")
                continue

            # If issuer CIK is different from filing CIK, update the company association
            if issuer_cik != filing.cik:
                from app.models.company import Company

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
                old_cik = filing.cik
                filing.company_id = issuer_company.id
                filing.cik = issuer_cik
                filing.ticker = issuer_company.ticker

                LOGGER.info(f"Updated failed filing {filing.accession_number}: CIK {old_cik} -> {issuer_cik}")

        await session.commit()
        LOGGER.info("Re-processing of failed Form 4 filings complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(reprocess_failed_form4_filings())