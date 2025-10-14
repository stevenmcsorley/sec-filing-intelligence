"""
Filing Correlation Service

Calculates the correlation between SEC filings and stock price movements.
This service analyzes filing dates against price data to determine:
- Price change percentage around filing dates
- Volume spikes during filing periods
- Correlation strength between filing types and market impact
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.config import get_settings
from app.models.filing import Filing
from app.services.price_data import PriceDataService
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

LOGGER = logging.getLogger(__name__)

@dataclass
class FilingCorrelationData:
    """Data structure for filing correlation analysis"""
    filing_id: str
    ticker: str
    form_type: str
    filing_date: str
    title: str
    
    # Price analysis
    price_change_percent: float
    volume_spike_ratio: float
    price_volatility: float
    
    # Correlation metrics
    correlation_strength: str  # 'strong', 'moderate', 'weak'
    market_impact_score: float  # 0-100
    confidence_level: float  # 0-1
    
    # Additional context
    days_before_filing: int
    days_after_filing: int
    sector_impact: str | None = None

class FilingCorrelationService:
    """Service for analyzing correlations between SEC filings and stock price movements"""
    
    def __init__(self, db_session: AsyncSession, price_service: PriceDataService):
        self._db = db_session
        self._price_service = price_service
        self._settings = get_settings()
    
    async def analyze_filing_correlations(
        self, 
        ticker: str, 
        days_lookback: int = 30,
        min_price_change: float = 1.0
    ) -> list[FilingCorrelationData]:
        """
        Analyze correlations between filings and price movements for a given ticker
        
        Args:
            ticker: Stock ticker symbol
            days_lookback: Number of days to look back for analysis
            min_price_change: Minimum price change percentage to consider significant
            
        Returns:
            List of filing correlation data
        """
        try:
            # Get filings for the ticker
            filings = await self._get_filings_for_ticker(ticker, days_lookback)
            
            if not filings:
                LOGGER.info(
                    f"No filings found for ticker {ticker} in the last {days_lookback} days"
                )
                return []
            
            # Get historical price data
            historical_prices = await self._price_service.get_historical_prices(
                ticker, days_lookback + 10
            )
            
            if not historical_prices:
                LOGGER.warning(f"No price data available for ticker {ticker}")
                return []
            
            # Analyze each filing
            correlations = []
            for filing in filings:
                correlation = await self._analyze_single_filing_correlation(
                    filing, historical_prices, ticker
                )
                if correlation and abs(correlation.price_change_percent) >= min_price_change:
                    correlations.append(correlation)
            
            # Sort by market impact score (highest first)
            correlations.sort(key=lambda x: x.market_impact_score, reverse=True)
            
            LOGGER.info(f"Analyzed {len(correlations)} filing correlations for {ticker}")
            return correlations
            
        except Exception as e:
            LOGGER.error(f"Error analyzing filing correlations for {ticker}: {e}")
            return []
    
    async def _get_filings_for_ticker(
        self, 
        ticker: str, 
        days_lookback: int
    ) -> list[Filing]:
        """Get filings for a specific ticker within the lookback period"""
        cutoff_date = datetime.now() - timedelta(days=days_lookback)
        
        query = select(Filing).where(
            and_(
                Filing.ticker == ticker,
                Filing.filed_at >= cutoff_date
            )
        ).order_by(Filing.filed_at.desc())
        
        result = await self._db.execute(query)
        return result.scalars().all()
    
    async def _analyze_single_filing_correlation(
        self, 
        filing: Filing, 
        historical_prices: list[dict[str, Any]], 
        ticker: str
    ) -> FilingCorrelationData | None:
        """Analyze correlation for a single filing"""
        try:
            filing_date = filing.filed_at.date()
            
            # Find price data around the filing date
            price_data = self._get_price_data_around_filing(filing_date, historical_prices)
            
            if not price_data:
                return None
            
            # Calculate price change
            price_change_percent = self._calculate_price_change_percent(price_data)
            
            # Calculate volume spike
            volume_spike_ratio = self._calculate_volume_spike_ratio(price_data)
            
            # Calculate volatility
            price_volatility = self._calculate_price_volatility(price_data)
            
            # Determine correlation strength
            correlation_strength = self._determine_correlation_strength(
                price_change_percent, volume_spike_ratio, filing.form_type
            )
            
            # Calculate market impact score
            market_impact_score = self._calculate_market_impact_score(
                price_change_percent, volume_spike_ratio, price_volatility, filing.form_type
            )
            
            # Calculate confidence level
            confidence_level = self._calculate_confidence_level(
                price_change_percent, volume_spike_ratio, filing.form_type
            )
            
            return FilingCorrelationData(
                filing_id=str(filing.id),
                ticker=ticker,
                form_type=filing.form_type,
                filing_date=filing_date.isoformat(),
                title=filing.company_name or f"{filing.form_type} Filing",
                price_change_percent=price_change_percent,
                volume_spike_ratio=volume_spike_ratio,
                price_volatility=price_volatility,
                correlation_strength=correlation_strength,
                market_impact_score=market_impact_score,
                confidence_level=confidence_level,
                days_before_filing=len(price_data.get('before', [])),
                days_after_filing=len(price_data.get('after', []))
            )
            
        except Exception as e:
            LOGGER.error(f"Error analyzing filing correlation for {filing.id}: {e}")
            return None
    
    def _get_price_data_around_filing(
        self, 
        filing_date: datetime.date, 
        historical_prices: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]] | None:
        """Get price data before and after filing date"""
        try:
            # Convert historical prices to date-keyed dict
            price_dict = {}
            for price in historical_prices:
                price_date = datetime.fromisoformat(price['date']).date()
                price_dict[price_date] = price
            
            # Find the closest trading day to filing date
            filing_price_data = None
            for days_offset in range(5):  # Look up to 5 days before/after
                check_date = filing_date - timedelta(days=days_offset)
                if check_date in price_dict:
                    filing_price_data = price_dict[check_date]
                    break
            
            if not filing_price_data:
                return None
            
            # Get price data before filing (up to 5 days)
            before_prices = []
            for i in range(1, 6):
                check_date = filing_date - timedelta(days=i)
                if check_date in price_dict:
                    before_prices.append(price_dict[check_date])
            
            # Get price data after filing (up to 5 days)
            after_prices = []
            for i in range(1, 6):
                check_date = filing_date + timedelta(days=i)
                if check_date in price_dict:
                    after_prices.append(price_dict[check_date])
            
            return {
                'filing_day': filing_price_data,
                'before': before_prices,
                'after': after_prices
            }
            
        except Exception as e:
            LOGGER.error(f"Error getting price data around filing date {filing_date}: {e}")
            return None
    
    def _calculate_price_change_percent(self, price_data: dict[str, list[dict[str, Any]]]) -> float:
        """Calculate price change percentage around filing"""
        try:
            # filing_day = price_data['filing_day']  # Not used in calculation
            before_prices = price_data['before']
            after_prices = price_data['after']
            
            if not before_prices or not after_prices:
                return 0.0
            
            # Use average price before filing as baseline
            avg_price_before = sum(p['close'] for p in before_prices) / len(before_prices)
            
            # Use average price after filing
            avg_price_after = sum(p['close'] for p in after_prices) / len(after_prices)
            
            # Calculate percentage change
            if avg_price_before == 0:
                return 0.0
            
            return ((avg_price_after - avg_price_before) / avg_price_before) * 100
            
        except Exception as e:
            LOGGER.error(f"Error calculating price change percent: {e}")
            return 0.0
    
    def _calculate_volume_spike_ratio(self, price_data: dict[str, list[dict[str, Any]]]) -> float:
        """Calculate volume spike ratio around filing"""
        try:
            filing_day = price_data['filing_day']
            before_prices = price_data['before']
            
            if not before_prices:
                return 1.0
            
            # Calculate average volume before filing
            avg_volume_before = sum(p['volume'] for p in before_prices) / len(before_prices)
            
            # Calculate volume spike ratio
            if avg_volume_before == 0:
                return 1.0
            
            return filing_day['volume'] / avg_volume_before
            
        except Exception as e:
            LOGGER.error(f"Error calculating volume spike ratio: {e}")
            return 1.0
    
    def _calculate_price_volatility(self, price_data: dict[str, list[dict[str, Any]]]) -> float:
        """Calculate price volatility around filing"""
        try:
            all_prices = []
            all_prices.extend(price_data['before'])
            all_prices.append(price_data['filing_day'])
            all_prices.extend(price_data['after'])
            
            if len(all_prices) < 2:
                return 0.0
            
            # Calculate standard deviation of closing prices
            closes = [p['close'] for p in all_prices]
            mean_close = sum(closes) / len(closes)
            variance = sum((close - mean_close) ** 2 for close in closes) / len(closes)
            
            return variance ** 0.5
            
        except Exception as e:
            LOGGER.error(f"Error calculating price volatility: {e}")
            return 0.0
    
    def _determine_correlation_strength(
        self, 
        price_change_percent: float, 
        volume_spike_ratio: float, 
        form_type: str
    ) -> str:
        """Determine correlation strength based on metrics"""
        # High impact forms (8-K, 4) with significant price/volume changes
        if form_type in ['8-K', '4'] and abs(price_change_percent) > 5 and volume_spike_ratio > 1.5:
            return 'strong'
        
        # Medium impact forms or moderate changes
        if (form_type in ['10-K', '10-Q', 'S-1'] and abs(price_change_percent) > 2) or \
           (abs(price_change_percent) > 3 and volume_spike_ratio > 1.2):
            return 'moderate'
        
        # Low impact or minimal changes
        return 'weak'
    
    def _calculate_market_impact_score(
        self, 
        price_change_percent: float, 
        volume_spike_ratio: float, 
        price_volatility: float, 
        form_type: str
    ) -> float:
        """Calculate market impact score (0-100)"""
        # Base score from price change (0-40 points)
        price_score = min(abs(price_change_percent) * 4, 40)
        
        # Volume spike score (0-30 points)
        volume_score = min((volume_spike_ratio - 1) * 15, 30)
        
        # Form type multiplier (0-30 points)
        form_multipliers = {
            '8-K': 30,  # Material events
            '4': 25,    # Insider trading
            '10-K': 20, # Annual reports
            '10-Q': 15, # Quarterly reports
            'S-1': 20,  # Registration statements
            '13D': 25,  # Beneficial ownership
            '13G': 20,  # Beneficial ownership (passive)
            '144': 10,  # Rule 144 sales
            '3': 5      # Initial statements
        }
        form_score = form_multipliers.get(form_type, 5)
        
        return min(price_score + volume_score + form_score, 100)
    
    def _calculate_confidence_level(
        self, 
        price_change_percent: float, 
        volume_spike_ratio: float, 
        form_type: str
    ) -> float:
        """Calculate confidence level (0-1) for the correlation"""
        # Higher confidence for significant changes
        confidence = 0.5  # Base confidence
        
        # Increase confidence for significant price changes
        if abs(price_change_percent) > 5:
            confidence += 0.2
        elif abs(price_change_percent) > 2:
            confidence += 0.1
        
        # Increase confidence for volume spikes
        if volume_spike_ratio > 2:
            confidence += 0.2
        elif volume_spike_ratio > 1.5:
            confidence += 0.1
        
        # Increase confidence for high-impact form types
        if form_type in ['8-K', '4', '13D']:
            confidence += 0.1
        
        return min(confidence, 1.0)
