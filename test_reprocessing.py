#!/usr/bin/env python3
"""
Test Script for SEC Filing Reprocessing
Tests the reprocessing on a small batch of filings first
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
from sqlalchemy import select, delete
from redis.asyncio import Redis

class TestReprocessor:
    """Test reprocessing on a small batch of filings."""
    
    def __init__(self):
        self.settings = Settings()
        self.redis_client = Redis.from_url(self.settings.redis_url)
        self.ticker_service = TickerLookupService(redis_client=self.redis_client)
        self.analyzer = RuleBasedAnalyzer()
        
    async def get_test_filings(self, limit: int = 5) -> List[Filing]:
        """Get a small batch of test filings."""
        print(f"📋 Fetching {limit} test filings...")
        
        async with get_db_session(self.settings) as session:
            # Get a mix of different form types
            stmt = select(Filing).order_by(Filing.filed_at.desc()).limit(limit)
            result = await session.execute(stmt)
            filings = result.scalars().all()
            
            print(f"   Found {len(filings)} test filings:")
            for filing in filings:
                print(f"     - {filing.accession_number} ({filing.form_type}) - {filing.ticker or 'No ticker'}")
            
            return filings
    
    async def get_filing_sections(self, filing_id: int) -> List[FilingSection]:
        """Get all sections for a filing."""
        async with get_db_session(self.settings) as session:
            stmt = select(FilingSection).where(FilingSection.filing_id == filing_id)
            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def test_enhanced_ticker_lookup(self, filing: Filing) -> bool:
        """Test enhanced ticker lookup."""
        print(f"\n🔍 Testing enhanced ticker lookup for {filing.cik}")
        
        try:
            # Test the enhanced ticker service
            company_info = await self.ticker_service.get_company_info_for_cik(filing.cik)
            
            if company_info:
                print(f"   ✅ Company info retrieved:")
                print(f"     Company: {company_info.get('company_name', 'N/A')}")
                print(f"     Ticker: {company_info.get('ticker', 'N/A')}")
                print(f"     CIK: {company_info.get('cik', 'N/A')}")
                return True
            else:
                print(f"   ⚠️  No company info found for CIK: {filing.cik}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error testing ticker lookup: {e}")
            return False
    
    async def test_rule_based_analysis(self, filing: Filing) -> bool:
        """Test rule-based analysis."""
        print(f"\n🧠 Testing rule-based analysis for {filing.form_type}")
        
        try:
            # Get filing sections
            sections = await self.get_filing_sections(filing.id)
            print(f"   📄 Found {len(sections)} sections")
            
            # Perform rule-based pre-analysis
            pre_analysis = await self.analyzer.analyze_filing(filing, sections)
            
            print(f"   ✅ Pre-analysis results:")
            print(f"     Priority: {pre_analysis.priority.value}")
            print(f"     Category: {pre_analysis.category.value}")
            print(f"     Confidence: {pre_analysis.confidence:.2f}")
            print(f"     Should use Groq: {pre_analysis.should_use_groq}")
            print(f"     Key findings: {len(pre_analysis.key_findings)}")
            print(f"     Estimated tokens: {pre_analysis.estimated_tokens}")
            
            if pre_analysis.key_findings:
                print(f"     Sample findings: {pre_analysis.key_findings[:3]}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error testing rule-based analysis: {e}")
            return False
    
    async def test_full_reprocessing(self, filing: Filing) -> bool:
        """Test full reprocessing workflow."""
        print(f"\n🔄 Testing full reprocessing for {filing.accession_number}")
        
        try:
            # Step 1: Enhanced ticker lookup
            ticker_success = await self.test_enhanced_ticker_lookup(filing)
            
            # Step 2: Rule-based analysis
            analysis_success = await self.test_rule_based_analysis(filing)
            
            # Step 3: Create test analysis (without saving to DB)
            if analysis_success:
                sections = await self.get_filing_sections(filing.id)
                pre_analysis = await self.analyzer.analyze_filing(filing, sections)
                
                analysis_content = {
                    "summary": pre_analysis.key_findings,
                    "priority": pre_analysis.priority.value,
                    "category": pre_analysis.category.value,
                    "confidence": pre_analysis.confidence,
                    "rule_based": True,
                    "should_use_groq": pre_analysis.should_use_groq,
                    "groq_prompt_focus": pre_analysis.groq_prompt_focus,
                    "estimated_tokens": pre_analysis.estimated_tokens,
                    "test_mode": True
                }
                
                print(f"   ✅ Test analysis content created:")
                print(f"     Content length: {len(json.dumps(analysis_content))} characters")
                print(f"     Would save to database: Yes")
            
            return ticker_success and analysis_success
            
        except Exception as e:
            print(f"   ❌ Error in full reprocessing test: {e}")
            return False
    
    async def run_test(self):
        """Run the test reprocessing."""
        print("🧪 Testing SEC Filing Reprocessing")
        print("=" * 50)
        
        # Get test filings
        test_filings = await self.get_test_filings(5)
        
        if not test_filings:
            print("❌ No test filings found")
            return
        
        # Test each filing
        results = {
            'total': len(test_filings),
            'ticker_success': 0,
            'analysis_success': 0,
            'full_success': 0
        }
        
        for filing in test_filings:
            print(f"\n{'='*60}")
            print(f"Testing filing: {filing.accession_number}")
            print(f"{'='*60}")
            
            # Test ticker lookup
            if await self.test_enhanced_ticker_lookup(filing):
                results['ticker_success'] += 1
            
            # Test rule-based analysis
            if await self.test_rule_based_analysis(filing):
                results['analysis_success'] += 1
            
            # Test full workflow
            if await self.test_full_reprocessing(filing):
                results['full_success'] += 1
        
        # Print results
        print(f"\n{'='*60}")
        print("🎯 TEST RESULTS SUMMARY")
        print(f"{'='*60}")
        print(f"Total filings tested: {results['total']}")
        print(f"Ticker lookup success: {results['ticker_success']}/{results['total']} ({results['ticker_success']/results['total']*100:.1f}%)")
        print(f"Analysis success: {results['analysis_success']}/{results['total']} ({results['analysis_success']/results['total']*100:.1f}%)")
        print(f"Full workflow success: {results['full_success']}/{results['total']} ({results['full_success']/results['total']*100:.1f}%)")
        
        if results['full_success'] == results['total']:
            print("\n✅ All tests passed! Ready for full reprocessing.")
        else:
            print(f"\n⚠️  {results['total'] - results['full_success']} tests failed. Review issues before full reprocessing.")

async def main():
    """Main entry point."""
    print("🧪 SEC Filing Reprocessing Test Tool")
    print("This will test the reprocessing on a small batch of filings")
    print()
    
    tester = TestReprocessor()
    await tester.run_test()

if __name__ == "__main__":
    asyncio.run(main())
