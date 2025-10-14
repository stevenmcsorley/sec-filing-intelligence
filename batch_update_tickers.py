#!/usr/bin/env python3
"""
Batch update script to add ticker information to all existing filings.
This will process filings that should have tickers but don't.
"""

import asyncio
import sys
import os
sys.path.append('backend')

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db_session
from app.config import Settings
from app.models.filing import Filing
from app.services.ticker_lookup import TickerLookupService
from redis.asyncio import Redis

async def batch_update_tickers():
    """Batch update ticker information for all filings that should have tickers."""
    settings = Settings()
    
    # Initialize Redis client for caching
    redis_client = Redis.from_url(settings.redis_url)
    ticker_service = TickerLookupService(redis_client=redis_client)
    
    async with get_db_session(settings) as session:
        # Find all filings that should have tickers but don't
        stmt = select(Filing).where(
            Filing.form_type.in_(['4', '10-K', '10-Q', '8-K', '144', '3', 'SCHEDULE 13D/A']),
            Filing.ticker.is_(None)
        )
        
        result = await session.execute(stmt)
        filings = result.scalars().all()
        
        print(f"Found {len(filings)} filings without tickers to process")
        
        updated_count = 0
        failed_count = 0
        processed_count = 0
        
        for filing in filings:
            processed_count += 1
            print(f"[{processed_count}/{len(filings)}] Processing filing {filing.id}: {filing.form_type} for CIK {filing.cik}")
            
            try:
                # Look up ticker for the filing's CIK
                ticker = await ticker_service.get_ticker_for_cik(filing.cik)
                
                if ticker:
                    # Update filing ticker using raw SQL
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
                    failed_count += 1
                    
            except Exception as e:
                print(f"  ⚠️  Error processing filing {filing.id}: {e}")
                failed_count += 1
            
            # Commit every 10 updates to avoid long transactions
            if processed_count % 10 == 0:
                await session.commit()
                print(f"  💾 Committed batch at {processed_count} filings")
        
        # Final commit
        await session.commit()
        
        print(f"\n🎯 Batch Update Complete!")
        print(f"  📊 Total processed: {processed_count}")
        print(f"  ✅ Successfully updated: {updated_count}")
        print(f"  ❌ Failed/No ticker found: {failed_count}")
        print(f"  📈 Success rate: {(updated_count/processed_count)*100:.1f}%")

if __name__ == "__main__":
    asyncio.run(batch_update_tickers())
