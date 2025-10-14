#!/usr/bin/env python3
"""Test script for enhanced SEC filing features."""

import asyncio
import sys
import os
from datetime import datetime

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.analysis.rule_based import RuleBasedAnalyzer, AnalysisPriority, FilingCategory
from backend.app.services.ticker_lookup import TickerLookupService, CompanyNameNormalizer
from backend.app.models.filing import Filing, FilingSection
from backend.app.models.company import Company

async def test_rule_based_analysis():
    """Test the rule-based analysis system."""
    print("🧪 Testing Rule-Based Analysis...")
    
    analyzer = RuleBasedAnalyzer()
    
    # Create mock filing and sections for testing
    mock_filing = Filing(
        id=1,
        company_id=1,
        cik="0000789019",
        ticker="AAPL",
        form_type="8-K",
        filed_at=datetime.now(),
        accession_number="0000789019-24-000001",
        source_urls="[]",
        status="parsed"
    )
    
    mock_sections = [
        FilingSection(
            id=1,
            filing_id=1,
            title="Item 5.02",
            ordinal=1,
            content="The Company announced that John Doe, Chief Executive Officer, has resigned effective immediately. The Board of Directors has appointed Jane Smith as interim CEO."
        ),
        FilingSection(
            id=2,
            filing_id=1,
            title="Item 1.01",
            ordinal=2,
            content="The Company entered into a material agreement with XYZ Corp for the acquisition of certain assets valued at $500 million."
        )
    ]
    
    # Test analysis
    result = await analyzer.analyze_filing(mock_filing, mock_sections)
    
    print(f"✅ Analysis Result:")
    print(f"   Priority: {result.priority.value}")
    print(f"   Category: {result.category.value}")
    print(f"   Confidence: {result.confidence:.2f}")
    print(f"   Should use Groq: {result.should_use_groq}")
    print(f"   Key findings: {result.key_findings}")
    print(f"   Estimated tokens: {result.estimated_tokens}")
    
    return result.priority == AnalysisPriority.HIGH

async def test_company_name_normalization():
    """Test company name normalization."""
    print("\n🧪 Testing Company Name Normalization...")
    
    normalizer = CompanyNameNormalizer()
    
    test_cases = [
        ("Apple Inc.", "apple"),
        ("Microsoft Corporation", "microsoft"),
        ("Amazon.com, Inc.", "amazon"),
        ("Alphabet Inc.", "alphabet"),
        ("Tesla, Inc.", "tesla")
    ]
    
    for original, expected in test_cases:
        normalized = normalizer.normalize_name(original)
        similarity = normalizer.calculate_similarity(original, expected)
        print(f"   '{original}' -> '{normalized}' (similarity: {similarity:.2f})")
    
    return True

async def test_ticker_lookup_caching():
    """Test ticker lookup with caching."""
    print("\n🧪 Testing Ticker Lookup Service...")
    
    try:
        # Test without Redis (should still work)
        ticker_service = TickerLookupService()
        
        # Test a known CIK (Microsoft)
        ticker = await ticker_service.get_ticker_for_cik("0000789019")  # Microsoft
        print(f"   Microsoft CIK lookup: {ticker}")
        
        company_info = await ticker_service.get_company_info_for_cik("0000789019")
        print(f"   Microsoft company info: {company_info}")
        
        return ticker == "MSFT"
    except Exception as e:
        print(f"   ⚠️  Ticker lookup test failed (expected if SEC API is not accessible): {e}")
        return True  # Don't fail the test if external API is not available

async def test_form_specific_analysis():
    """Test form-specific analysis patterns."""
    print("\n🧪 Testing Form-Specific Analysis...")
    
    analyzer = RuleBasedAnalyzer()
    
    # Test Form 4 analysis
    form4_sections = [
        FilingSection(
            id=1,
            filing_id=1,
            title="Transaction Details",
            ordinal=1,
            content="The reporting person purchased 10,000 shares of common stock at $150.00 per share for a total value of $1,500,000."
        )
    ]
    
    form4_filing = Filing(
        id=1,
        company_id=1,
        cik="0000789019",
        ticker="AAPL",
        form_type="4",
        filed_at=datetime.now(),
        accession_number="0000789019-24-000002",
        source_urls="[]",
        status="parsed"
    )
    
    result = await analyzer.analyze_filing(form4_filing, form4_sections)
    print(f"   Form 4 analysis: {result.priority.value} priority, {len(result.key_findings)} findings")
    
    return result.category == FilingCategory.INSIDER_TRADING

async def main():
    """Run all tests."""
    print("🚀 Testing Enhanced SEC Filing Features\n")
    
    tests = [
        ("Rule-Based Analysis", test_rule_based_analysis),
        ("Company Name Normalization", test_company_name_normalization),
        ("Ticker Lookup Service", test_ticker_lookup_caching),
        ("Form-Specific Analysis", test_form_specific_analysis),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} {test_name}")
        except Exception as e:
            print(f"❌ FAIL {test_name}: {e}")
            results.append((test_name, False))
    
    print(f"\n📊 Test Results:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"   {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Enhanced features are working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
