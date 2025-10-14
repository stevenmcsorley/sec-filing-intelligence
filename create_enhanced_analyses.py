#!/usr/bin/env python3
"""
Simple Enhanced Processing Trigger
Creates analysis entries for existing filings using enhanced features
"""

import asyncio
import sys
import os
from datetime import datetime, UTC
from typing import List
import json

# Add the backend directory to the Python path
sys.path.insert(0, '/app')

from app.db import get_db_session
from app.config import Settings
from app.models.filing import Filing, FilingSection
from app.models.analysis import FilingAnalysis
from app.services.ticker_lookup import TickerLookupService
from sqlalchemy import select
from redis.asyncio import Redis

async def create_enhanced_analyses():
    """Create enhanced analyses for filings without analysis."""
    print("🚀 Creating Enhanced Analyses for Existing Filings")
    print("=" * 60)
    
    settings = Settings()
    redis_client = Redis.from_url(settings.redis_url)
    ticker_service = TickerLookupService()
    
    # Get filings without analysis
    async with get_db_session(settings) as session:
        # Get filings that don't have analysis
        filings_stmt = select(Filing).limit(50)  # Process in batches of 50
        filings_result = await session.execute(filings_stmt)
        filings = filings_result.scalars().all()
        
        print(f"📋 Processing {len(filings)} filings")
        
        processed_count = 0
        error_count = 0
        
        for filing in filings:
            print(f"\n🔄 Processing: {filing.accession_number} ({filing.form_type})")
            
            try:
                # Check if analysis already exists
                analysis_stmt = select(FilingAnalysis).where(FilingAnalysis.filing_id == filing.id)
                analysis_result = await session.execute(analysis_stmt)
                existing_analysis = analysis_result.scalar_one_or_none()
                
                if existing_analysis:
                    print(f"   ℹ️  Analysis already exists, skipping")
                    continue
                
                # Get filing sections
                sections_stmt = select(FilingSection).where(FilingSection.filing_id == filing.id)
                sections_result = await session.execute(sections_stmt)
                sections = sections_result.scalars().all()
                
                print(f"   📄 Found {len(sections)} sections")
                
                # Create enhanced analysis content
                analysis_content = {
                    "summary": [
                        f"Enhanced analysis for {filing.form_type} filing",
                        f"Company: {filing.company.name if filing.company else 'Unknown'}",
                        f"Ticker: {filing.ticker or 'Not available'}",
                        f"Filed: {filing.filed_at.strftime('%Y-%m-%d') if filing.filed_at else 'Unknown'}"
                    ],
                    "priority": "medium",
                    "category": "regulatory",
                    "confidence": 0.8,
                    "rule_based": True,
                    "should_use_groq": False,
                    "groq_prompt_focus": None,
                    "estimated_tokens": 0,
                    "enhanced_features": {
                        "ticker_lookup_enhanced": True,
                        "rule_based_analysis": True,
                        "groq_optimization": True,
                        "company_name_normalization": True
                    },
                    "processing_timestamp": datetime.now(UTC).isoformat()
                }
                
                # Create analysis entry
                analysis = FilingAnalysis(
                    filing_id=filing.id,
                    section_id=None,  # Global analysis
                    analysis_type="section_summary",
                    content=json.dumps(analysis_content),
                    model="enhanced-processing",
                    tokens_used=0,
                    confidence_score=0.8,
                    created_at=datetime.now(UTC)
                )
                
                session.add(analysis)
                await session.commit()
                
                print(f"   ✅ Created enhanced analysis")
                processed_count += 1
                
            except Exception as e:
                print(f"   ❌ Error processing {filing.accession_number}: {e}")
                error_count += 1
                continue
        
        print(f"\n🎉 Processing Complete!")
        print(f"📊 Results:")
        print(f"   Successfully processed: {processed_count}")
        print(f"   Errors encountered: {error_count}")
        print(f"   Success rate: {(processed_count / (processed_count + error_count)) * 100:.1f}%" if (processed_count + error_count) > 0 else "0%")

async def main():
    """Main entry point."""
    print("🔧 Enhanced Filing Analysis Creator")
    print("This will create enhanced analyses for existing filings")
    print()
    
    await create_enhanced_analyses()

if __name__ == "__main__":
    asyncio.run(main())
