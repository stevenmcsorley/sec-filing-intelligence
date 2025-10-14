#!/usr/bin/env python3
"""
Direct database update script to add ticker information to filings.
This bypasses the Docker build issues and directly updates the database.
"""

import asyncio
import sys
import os
sys.path.append('backend')

from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db_session
from app.config import Settings
from app.models.filing import Filing
from app.models.company import Company
from app.services.ticker_lookup import TickerLookupService
from redis.asyncio import Redis

async def update_ticker_information():
    """Update ticker information for filings that should have tickers."""
    settings = Settings()
    
    # Initialize Redis client for caching
    redis_client = Redis.from_url(settings.redis_url)
    ticker_service = TickerLookupService(redis_client=redis_client)
    
    async with get_db_session(settings) as session:
        # Find filings that should have tickers but don't
        stmt = select(Filing).where(
            Filing.form_type.in_(['4', '10-K', '10-Q', '8-K', '144']),
            Filing.ticker.is_(None)
        ).limit(50)  # Process 50 at a time
        
        result = await session.execute(stmt)
        filings = result.scalars().all()
        
        print(f"Found {len(filings)} filings without tickers to process")
        
        updated_count = 0
        for filing in filings:
            print(f"Processing filing {filing.id}: {filing.form_type} for CIK {filing.cik}")
            
            # Look up ticker for the filing's CIK
            ticker = await ticker_service.get_ticker_for_cik(filing.cik)
            
            if ticker:
                # Update filing ticker using raw SQL to bypass ORM issues
                await session.execute(
                    text("UPDATE filings SET ticker = :ticker WHERE id = :filing_id"),
                    {"ticker": ticker, "filing_id": filing.id}
                )
                
                # Update company ticker if it's missing
                if filing.company and not filing.company.ticker:
                    await session.execute(
                        text("UPDATE companies SET ticker = :ticker WHERE id = :company_id"),
                        {"ticker": ticker, "company_id": filing.company.id}
                    )
                    
                updated_count += 1
                print(f"  ✅ Updated ticker: {ticker}")
            else:
                print(f"  ❌ No ticker found for CIK {filing.cik}")
        
        # Commit all changes
        await session.commit()
        print(f"\n✅ Successfully updated {updated_count} filings with ticker information")
        
        # Show some examples
        if updated_count > 0:
            print("\nUpdated filings:")
            for filing in filings[:5]:  # Show first 5
                if filing.ticker:
                    print(f"  - {filing.form_type} | CIK: {filing.cik} | Ticker: {filing.ticker}")

if __name__ == "__main__":
    asyncio.run(update_ticker_information())
