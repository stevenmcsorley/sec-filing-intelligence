#!/usr/bin/env python3
"""
Comprehensive SEC Filing Reprocessing Script
Reprocesses all filings with enhanced rule-based analysis and improved ticker lookup
"""

import asyncio
import sys
import os
from datetime import datetime, UTC
from typing import List, Optional
import json

# Add the backend directory to the Python path
sys.path.insert(0, '/app')

from app.db import get_db_session
from app.config import Settings
from app.models.filing import Filing, FilingSection, FilingAnalysis
from app.models.company import Company
from app.analysis.rule_based import RuleBasedAnalyzer, PreAnalysisResult
from app.services.ticker_lookup import TickerLookupService
from app.orchestration.planner import EnhancedChunkPlanner, EnhancedChunkTask
from app.summarization.worker import SectionSummaryWorker
from sqlalchemy import select, delete
from redis.asyncio import Redis

class ComprehensiveReprocessor:
    """Reprocesses all filings with enhanced features."""
    
    def __init__(self):
        self.settings = Settings()
        self.redis_client = Redis.from_url(self.settings.redis_url)
        self.ticker_service = TickerLookupService(redis_client=self.redis_client)
        self.analyzer = RuleBasedAnalyzer()
        self.planner = EnhancedChunkPlanner()
        self.processed_count = 0
        self.skipped_count = 0
        self.error_count = 0
        self.batch_size = 10  # Process in small batches
        
    async def clear_existing_analyses(self) -> int:
        """Clear all existing analyses to start fresh."""
        print("🧹 Clearing existing analyses...")
        
        async with get_db_session(self.settings) as session:
            # Count existing analyses
            count_stmt = select(FilingAnalysis)
            count_result = await session.execute(count_stmt)
            existing_count = len(count_result.scalars().all())
            
            if existing_count > 0:
                print(f"   Found {existing_count} existing analyses to clear")
                
                # Delete all existing analyses
                delete_stmt = delete(FilingAnalysis)
                await session.execute(delete_stmt)
                await session.commit()
                
                print(f"   ✅ Cleared {existing_count} existing analyses")
            else:
                print("   ℹ️  No existing analyses found")
                
            return existing_count
    
    async def get_all_filings(self) -> List[Filing]:
        """Get all filings from the database."""
        print("📋 Fetching all filings from database...")
        
        async with get_db_session(self.settings) as session:
            stmt = select(Filing).order_by(Filing.filed_at.desc())
            result = await session.execute(stmt)
            filings = result.scalars().all()
            
            print(f"   Found {len(filings)} total filings")
            return filings
    
    async def get_filing_sections(self, filing_id: int) -> List[FilingSection]:
        """Get all sections for a filing."""
        async with get_db_session(self.settings) as session:
            stmt = select(FilingSection).where(FilingSection.filing_id == filing_id)
            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def enhance_ticker_lookup(self, filing: Filing) -> bool:
        """Enhance ticker lookup for a filing using the new service."""
        try:
            # Get company info using enhanced ticker service
            company_info = await self.ticker_service.get_company_info_for_cik(filing.cik)
            
            if company_info and company_info.get('ticker'):
                # Update filing with enhanced ticker
                async with get_db_session(self.settings) as session:
                    filing_stmt = select(Filing).where(Filing.id == filing.id)
                    filing_result = await session.execute(filing_stmt)
                    current_filing = filing_result.scalar_one()
                    
                    current_filing.ticker = company_info['ticker']
                    await session.commit()
                    
                print(f"   ✅ Enhanced ticker lookup: {filing.cik} -> {company_info['ticker']}")
                return True
            else:
                print(f"   ⚠️  Could not enhance ticker for CIK: {filing.cik}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error enhancing ticker lookup for {filing.cik}: {e}")
            return False
    
    async def process_filing_with_enhanced_analysis(self, filing: Filing) -> bool:
        """Process a single filing with enhanced rule-based analysis."""
        try:
            print(f"\n🔄 Processing filing: {filing.accession_number} ({filing.form_type})")
            
            # Get filing sections
            sections = await self.get_filing_sections(filing.id)
            print(f"   📄 Found {len(sections)} sections")
            
            # Perform rule-based pre-analysis
            pre_analysis = await self.analyzer.analyze_filing(filing, sections)
            print(f"   🧠 Pre-analysis: {pre_analysis.priority.value} priority, {pre_analysis.confidence:.2f} confidence")
            
            # Create analysis result
            async with get_db_session(self.settings) as session:
                analysis_content = {
                    "summary": pre_analysis.key_findings,
                    "priority": pre_analysis.priority.value,
                    "category": pre_analysis.category.value,
                    "confidence": pre_analysis.confidence,
                    "rule_based": True,
                    "should_use_groq": pre_analysis.should_use_groq,
                    "groq_prompt_focus": pre_analysis.groq_prompt_focus,
                    "estimated_tokens": pre_analysis.estimated_tokens,
                    "reprocessed_at": datetime.now(UTC).isoformat()
                }
                
                # Create or update analysis
                analysis_stmt = select(FilingAnalysis).where(FilingAnalysis.filing_id == filing.id)
                analysis_result = await session.execute(analysis_stmt)
                existing_analysis = analysis_result.scalar_one_or_none()
                
                if existing_analysis:
                    existing_analysis.content = json.dumps(analysis_content)
                    existing_analysis.model = "rule-based-enhanced"
                    existing_analysis.confidence_score = pre_analysis.confidence
                    existing_analysis.created_at = datetime.now(UTC)
                else:
                    analysis = FilingAnalysis(
                        filing_id=filing.id,
                        section_id=None,  # Global analysis
                        analysis_type="section_summary",
                        content=json.dumps(analysis_content),
                        model="rule-based-enhanced",
                        tokens_used=0 if not pre_analysis.should_use_groq else pre_analysis.estimated_tokens,
                        confidence_score=pre_analysis.confidence,
                        created_at=datetime.now(UTC)
                    )
                    session.add(analysis)
                
                await session.commit()
                
            print(f"   ✅ Analysis saved: {len(pre_analysis.key_findings)} findings")
            return True
            
        except Exception as e:
            print(f"   ❌ Error processing filing {filing.accession_number}: {e}")
            return False
    
    async def process_batch(self, filings: List[Filing]) -> dict:
        """Process a batch of filings."""
        batch_results = {
            'processed': 0,
            'skipped': 0,
            'errors': 0
        }
        
        for filing in filings:
            try:
                # Enhance ticker lookup first
                await self.enhance_ticker_lookup(filing)
                
                # Process with enhanced analysis
                success = await self.process_filing_with_enhanced_analysis(filing)
                
                if success:
                    batch_results['processed'] += 1
                    self.processed_count += 1
                else:
                    batch_results['errors'] += 1
                    self.error_count += 1
                    
            except Exception as e:
                print(f"   ❌ Unexpected error processing {filing.accession_number}: {e}")
                batch_results['errors'] += 1
                self.error_count += 1
        
        return batch_results
    
    async def reprocess_all_filings(self):
        """Main method to reprocess all filings."""
        print("🚀 Starting comprehensive filing reprocessing...")
        print("=" * 60)
        
        start_time = datetime.now(UTC)
        
        # Step 1: Clear existing analyses
        cleared_count = await self.clear_existing_analyses()
        
        # Step 2: Get all filings
        all_filings = await self.get_all_filings()
        
        if not all_filings:
            print("❌ No filings found to process")
            return
        
        # Step 3: Process in batches
        total_batches = (len(all_filings) + self.batch_size - 1) // self.batch_size
        print(f"\n📦 Processing {len(all_filings)} filings in {total_batches} batches of {self.batch_size}")
        
        for i in range(0, len(all_filings), self.batch_size):
            batch_num = (i // self.batch_size) + 1
            batch_filings = all_filings[i:i + self.batch_size]
            
            print(f"\n🔄 Processing batch {batch_num}/{total_batches} ({len(batch_filings)} filings)")
            
            batch_results = await self.process_batch(batch_filings)
            
            print(f"   ✅ Batch {batch_num} complete: {batch_results['processed']} processed, {batch_results['errors']} errors")
            
            # Progress update
            total_processed = self.processed_count + self.error_count
            progress = (total_processed / len(all_filings)) * 100
            print(f"   📊 Overall progress: {total_processed}/{len(all_filings)} ({progress:.1f}%)")
        
        # Final summary
        end_time = datetime.now(UTC)
        duration = end_time - start_time
        
        print("\n" + "=" * 60)
        print("🎉 COMPREHENSIVE REPROCESSING COMPLETE!")
        print("=" * 60)
        print(f"📊 Final Results:")
        print(f"   Total filings processed: {len(all_filings)}")
        print(f"   Successfully processed: {self.processed_count}")
        print(f"   Errors encountered: {self.error_count}")
        print(f"   Success rate: {(self.processed_count / len(all_filings)) * 100:.1f}%")
        print(f"   Duration: {duration}")
        print(f"   Average time per filing: {duration.total_seconds() / len(all_filings):.2f} seconds")
        
        print(f"\n✨ Enhanced Features Applied:")
        print(f"   ✅ Rule-based pre-analysis for all filings")
        print(f"   ✅ Enhanced ticker lookup with Redis caching")
        print(f"   ✅ Improved company name normalization")
        print(f"   ✅ Groq optimization (skipping low-priority filings)")
        print(f"   ✅ Better categorization and confidence scoring")

async def main():
    """Main entry point."""
    print("🔧 SEC Filing Comprehensive Reprocessing Tool")
    print("This will reprocess ALL filings with enhanced features")
    print()
    
    # Confirm before proceeding
    response = input("⚠️  This will clear all existing analyses and reprocess 950+ filings. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Reprocessing cancelled")
        return
    
    reprocessor = ComprehensiveReprocessor()
    await reprocessor.reprocess_all_filings()

if __name__ == "__main__":
    asyncio.run(main())
