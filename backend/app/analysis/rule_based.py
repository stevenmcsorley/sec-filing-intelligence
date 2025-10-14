"""Rule-based pre-analysis service to reduce Groq API usage and improve efficiency."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.models.filing import Filing, FilingSection

LOGGER = logging.getLogger(__name__)


class AnalysisPriority(Enum):
    """Priority levels for filing analysis."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SKIP = "skip"


class FilingCategory(Enum):
    """Categories of filing analysis."""
    INSIDER_TRADING = "insider_trading"
    EXECUTIVE_CHANGE = "executive_change"
    EARNINGS = "earnings"
    MERGER_ACQUISITION = "merger_acquisition"
    REGULATORY = "regulatory"
    ACCOUNTING = "accounting"
    ROUTINE = "routine"


@dataclass
class PreAnalysisResult:
    """Result of rule-based pre-analysis."""
    priority: AnalysisPriority
    category: FilingCategory
    confidence: float
    key_findings: list[str]
    should_use_groq: bool
    groq_prompt_focus: str | None
    estimated_tokens: int


class RuleBasedAnalyzer:
    """Performs rule-based analysis to reduce Groq usage and improve efficiency."""

    def __init__(self):
        # Define patterns for different filing types
        self._form_patterns = {
            "4": self._analyze_form4,
            "8-K": self._analyze_form8k,
            "10-K": self._analyze_form10k,
            "10-Q": self._analyze_form10q,
            "13D": self._analyze_schedule13d,
            "144": self._analyze_form144,
        }
        
        # Keywords that indicate high-impact events
        self._high_impact_keywords = {
            "ceo", "chief executive", "cfo", "chief financial", "departure", "resignation",
            "termination", "merger", "acquisition", "bankruptcy", "delisting", "going concern",
            "material weakness", "restatement", "auditor change", "going private"
        }
        
        # Keywords for insider trading analysis
        self._insider_keywords = {
            "purchase", "sale", "buy", "sell", "option", "exercise", "grant", "vest",
            "beneficial ownership", "insider", "officer", "director"
        }
        
        # Keywords for earnings analysis
        self._earnings_keywords = {
            "revenue", "earnings", "profit", "loss", "guidance", "forecast", "quarterly",
            "annual", "results", "performance", "beat", "miss"
        }

    async def analyze_filing(
        self, filing: Filing, sections: list[FilingSection]
    ) -> PreAnalysisResult:
        """Perform rule-based analysis on a filing."""
        form_type = filing.form_type
        
        # Get form-specific analysis
        if form_type in self._form_patterns:
            result = await self._form_patterns[form_type](filing, sections)
        else:
            result = await self._analyze_generic(filing, sections)
        
        # Adjust priority based on additional factors
        result = self._adjust_priority(filing, sections, result)
        
        LOGGER.info(
            f"Pre-analysis for filing {filing.accession_number}: "
            f"{result.priority.value} priority, {result.category.value} category"
        )
        return result

    async def _analyze_form4(
        self, filing: Filing, sections: list[FilingSection]
    ) -> PreAnalysisResult:
        """Analyze Form 4 (insider trading) filings."""
        key_findings = []
        confidence = 0.8
        
        # Extract transaction details from sections
        for section in sections:
            content = section.content.lower()
            
            # Look for transaction amounts
            amount_matches = re.findall(r'\$[\d,]+(?:\.\d{2})?', content)
            if amount_matches:
                amounts = [float(m.replace('$', '').replace(',', '')) for m in amount_matches]
                max_amount = max(amounts) if amounts else 0
                if max_amount > 1000000:  # $1M threshold
                    key_findings.append(f"Large transaction: ${max_amount:,.0f}")
                    confidence = 0.9
            
            # Look for transaction types
            if any(word in content for word in ["purchase", "buy"]):
                key_findings.append("Insider purchase")
            elif any(word in content for word in ["sale", "sell"]):
                key_findings.append("Insider sale")
            
            # Look for executive roles
            exec_roles = ["ceo", "chief executive", "cfo", "chief financial"]
            if any(word in content for word in exec_roles):
                key_findings.append("Executive transaction")
                confidence = 0.95
        
        # Determine priority based on findings
        if any("Large transaction" in finding for finding in key_findings):
            priority = AnalysisPriority.HIGH
        elif any("Executive" in finding for finding in key_findings):
            priority = AnalysisPriority.MEDIUM
        else:
            priority = AnalysisPriority.LOW
        
        return PreAnalysisResult(
            priority=priority,
            category=FilingCategory.INSIDER_TRADING,
            confidence=confidence,
            key_findings=key_findings,
            should_use_groq=priority in [AnalysisPriority.HIGH, AnalysisPriority.MEDIUM],
            groq_prompt_focus=(
                "Focus on transaction significance and insider role" 
                if priority != AnalysisPriority.LOW else None
            ),
            estimated_tokens=200 if priority == AnalysisPriority.HIGH else 100
        )

    async def _analyze_form8k(
        self, filing: Filing, sections: list[FilingSection]
    ) -> PreAnalysisResult:
        """Analyze Form 8-K (current report) filings."""
        key_findings = []
        confidence = 0.7
        
        # Combine all section content for analysis
        full_content = " ".join([s.content.lower() for s in sections])
        
        # Check for high-impact keywords
        high_impact_found = []
        for keyword in self._high_impact_keywords:
            if keyword in full_content:
                high_impact_found.append(keyword)
        
        if high_impact_found:
            key_findings.extend([f"High-impact event: {keyword}" for keyword in high_impact_found])
            confidence = 0.9
        
        # Look for specific item numbers
        item_matches = re.findall(r'item\s+(\d+\.\d+)', full_content)
        if item_matches:
            key_findings.append(f"Items reported: {', '.join(item_matches)}")
            
            # High-priority items
            high_priority_items = ["1.01", "2.02", "3.01", "4.01", "5.01", "5.02"]
            if any(item in item_matches for item in high_priority_items):
                confidence = 0.9
        
        # Determine priority
        if len(high_impact_found) > 2 or confidence > 0.85:
            priority = AnalysisPriority.HIGH
        elif len(high_impact_found) > 0 or confidence > 0.7:
            priority = AnalysisPriority.MEDIUM
        else:
            priority = AnalysisPriority.LOW
        
        return PreAnalysisResult(
            priority=priority,
            category=(
                FilingCategory.EXECUTIVE_CHANGE 
                if "departure" in high_impact_found 
                else FilingCategory.REGULATORY
            ),
            confidence=confidence,
            key_findings=key_findings,
            should_use_groq=priority in [AnalysisPriority.HIGH, AnalysisPriority.MEDIUM],
            groq_prompt_focus=(
                "Focus on material events and business impact" 
                if priority != AnalysisPriority.LOW else None
            ),
            estimated_tokens=300 if priority == AnalysisPriority.HIGH else 150
        )

    async def _analyze_form10k(
        self, filing: Filing, sections: list[FilingSection]
    ) -> PreAnalysisResult:
        """Analyze Form 10-K (annual report) filings."""
        key_findings = []
        confidence = 0.6
        
        # Look for risk factors and business changes
        for section in sections:
            content = section.content.lower()
            title = section.title.lower() if section.title else ""
            
            if "risk factors" in title or "risk" in title:
                if "going concern" in content:
                    key_findings.append("Going concern warning")
                    confidence = 0.95
                elif "material weakness" in content:
                    key_findings.append("Material weakness disclosed")
                    confidence = 0.9
            
            if "auditor" in content and ("change" in content or "resign" in content):
                key_findings.append("Auditor change")
                confidence = 0.9
        
        # Determine priority (10-Ks are generally lower priority unless they contain warnings)
        if confidence > 0.8:
            priority = AnalysisPriority.HIGH
        else:
            priority = AnalysisPriority.LOW
        
        return PreAnalysisResult(
            priority=priority,
            category=FilingCategory.ACCOUNTING,
            confidence=confidence,
            key_findings=key_findings,
            should_use_groq=priority == AnalysisPriority.HIGH,
            groq_prompt_focus=(
                "Focus on financial health and risk factors" 
                if priority == AnalysisPriority.HIGH else None
            ),
            estimated_tokens=500 if priority == AnalysisPriority.HIGH else 0
        )

    async def _analyze_form10q(
        self, filing: Filing, sections: list[FilingSection]
    ) -> PreAnalysisResult:
        """Analyze Form 10-Q (quarterly report) filings."""
        key_findings = []
        confidence = 0.6
        
        # Look for earnings-related content
        full_content = " ".join([s.content.lower() for s in sections])
        
        earnings_keywords_found = []
        for keyword in self._earnings_keywords:
            if keyword in full_content:
                earnings_keywords_found.append(keyword)
        
        if earnings_keywords_found:
            key_findings.append(f"Earnings content: {', '.join(earnings_keywords_found)}")
            confidence = 0.7
        
        # Look for guidance changes
        guidance_keywords = ["increase", "decrease"]
        if "guidance" in full_content and any(word in full_content for word in guidance_keywords):
            key_findings.append("Guidance change")
            confidence = 0.8
        
        # Determine priority
        if confidence > 0.75:
            priority = AnalysisPriority.MEDIUM
        else:
            priority = AnalysisPriority.LOW
        
        return PreAnalysisResult(
            priority=priority,
            category=FilingCategory.EARNINGS,
            confidence=confidence,
            key_findings=key_findings,
            should_use_groq=priority == AnalysisPriority.MEDIUM,
            groq_prompt_focus=(
                "Focus on quarterly performance and guidance" 
                if priority == AnalysisPriority.MEDIUM else None
            ),
            estimated_tokens=200 if priority == AnalysisPriority.MEDIUM else 0
        )

    async def _analyze_schedule13d(
        self, filing: Filing, sections: list[FilingSection]
    ) -> PreAnalysisResult:
        """Analyze Schedule 13D (beneficial ownership) filings."""
        key_findings = []
        confidence = 0.8
        
        # Look for activist language
        full_content = " ".join([s.content.lower() for s in sections])
        
        activist_keywords = ["activist", "proxy", "board", "management", "strategic", "value"]
        activist_found = [kw for kw in activist_keywords if kw in full_content]
        
        if activist_found:
            key_findings.append(f"Activist language: {', '.join(activist_found)}")
            confidence = 0.9
        
        # Look for ownership percentages
        ownership_matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', full_content)
        if ownership_matches:
            percentages = [float(p) for p in ownership_matches]
            max_ownership = max(percentages) if percentages else 0
            if max_ownership > 10:  # Significant ownership
                key_findings.append(f"Significant ownership: {max_ownership}%")
                confidence = 0.95
        
        priority = AnalysisPriority.HIGH if confidence > 0.85 else AnalysisPriority.MEDIUM
        
        return PreAnalysisResult(
            priority=priority,
            category=FilingCategory.MERGER_ACQUISITION,
            confidence=confidence,
            key_findings=key_findings,
            should_use_groq=True,
            groq_prompt_focus="Focus on activist intent and ownership strategy",
            estimated_tokens=250
        )

    async def _analyze_form144(
        self, filing: Filing, sections: list[FilingSection]
    ) -> PreAnalysisResult:
        """Analyze Form 144 (notice of proposed sale) filings."""
        key_findings = []
        confidence = 0.7
        
        # Look for sale volume
        full_content = " ".join([s.content.lower() for s in sections])
        
        volume_matches = re.findall(r'(\d+(?:,\d+)*)\s*shares', full_content)
        if volume_matches:
            volumes = [int(v.replace(',', '')) for v in volume_matches]
            max_volume = max(volumes) if volumes else 0
            if max_volume > 100000:  # Large volume threshold
                key_findings.append(f"Large volume sale: {max_volume:,} shares")
                confidence = 0.8
        
        priority = AnalysisPriority.MEDIUM if confidence > 0.75 else AnalysisPriority.LOW
        
        return PreAnalysisResult(
            priority=priority,
            category=FilingCategory.INSIDER_TRADING,
            confidence=confidence,
            key_findings=key_findings,
            should_use_groq=priority == AnalysisPriority.MEDIUM,
            groq_prompt_focus=(
                "Focus on sale timing and volume significance" 
                if priority == AnalysisPriority.MEDIUM else None
            ),
            estimated_tokens=100 if priority == AnalysisPriority.MEDIUM else 0
        )

    async def _analyze_generic(
        self, filing: Filing, sections: list[FilingSection]
    ) -> PreAnalysisResult:
        """Analyze generic filings using basic pattern matching."""
        key_findings = []
        confidence = 0.5
        
        # Basic keyword analysis
        full_content = " ".join([s.content.lower() for s in sections])
        
        if any(keyword in full_content for keyword in self._high_impact_keywords):
            key_findings.append("Contains high-impact keywords")
            confidence = 0.6
        
        priority = AnalysisPriority.LOW
        
        return PreAnalysisResult(
            priority=priority,
            category=FilingCategory.ROUTINE,
            confidence=confidence,
            key_findings=key_findings,
            should_use_groq=False,
            groq_prompt_focus=None,
            estimated_tokens=0
        )

    def _adjust_priority(
        self, filing: Filing, sections: list[FilingSection], result: PreAnalysisResult
    ) -> PreAnalysisResult:
        """Adjust priority based on additional factors."""
        # Check filing recency
        days_old = (datetime.now() - filing.filed_at).days
        if days_old < 1:  # Very recent filing
            if result.priority == AnalysisPriority.LOW:
                result.priority = AnalysisPriority.MEDIUM
                result.should_use_groq = True
                result.estimated_tokens = 100
        
        # Check for multiple high-impact findings
        if len(result.key_findings) > 3 and result.confidence > 0.8:
            result.priority = AnalysisPriority.HIGH
            result.should_use_groq = True
            result.estimated_tokens = max(result.estimated_tokens, 300)
        
        return result

    def get_analysis_summary(self, result: PreAnalysisResult) -> str:
        """Generate a human-readable summary of the analysis."""
        summary_parts = [
            f"Priority: {result.priority.value.title()}",
            f"Category: {result.category.value.replace('_', ' ').title()}",
            f"Confidence: {result.confidence:.1%}"
        ]
        
        if result.key_findings:
            summary_parts.append(f"Key findings: {', '.join(result.key_findings)}")
        
        if result.should_use_groq:
            summary_parts.append(f"Groq analysis: {result.estimated_tokens} tokens")
        else:
            summary_parts.append("Groq analysis: Skipped")
        
        return " | ".join(summary_parts)
