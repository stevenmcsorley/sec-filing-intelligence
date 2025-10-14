"""
API endpoints for filing correlation analysis
"""


from app.auth.dependencies import get_current_user_context
from app.db import get_db_session
from app.services.filing_correlation import FilingCorrelationService
from app.services.price_data import PriceDataService
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/correlation", tags=["correlation"])

async def _get_correlation_service(
    db: AsyncSession = Depends(get_db_session)  # noqa: B008
) -> FilingCorrelationService:
    """Dependency to provide FilingCorrelationService"""
    price_service = PriceDataService()
    return FilingCorrelationService(db, price_service)

@router.get("/filing/{ticker}")
async def get_filing_correlations(
    ticker: str,
    days_lookback: int = Query(30, ge=7, le=90, description="Days to look back for analysis"),
    min_price_change: float = Query(
        1.0, ge=0.0, le=50.0, description="Minimum price change percentage to include"
    ),
    correlation_service: FilingCorrelationService = Depends(_get_correlation_service),  # noqa: B008
    user_context: dict = Depends(get_current_user_context)  # noqa: B008
) -> list[dict]:
    """
    Get filing correlation analysis for a specific ticker
    
    Returns analysis of how SEC filings correlate with stock price movements
    """
    try:
        correlations = await correlation_service.analyze_filing_correlations(
            ticker=ticker.upper(),
            days_lookback=days_lookback,
            min_price_change=min_price_change
        )
        
        # Convert to dict format for JSON response
        return [
            {
                "filing_id": corr.filing_id,
                "ticker": corr.ticker,
                "form_type": corr.form_type,
                "filing_date": corr.filing_date,
                "title": corr.title,
                "price_change_percent": round(corr.price_change_percent, 2),
                "volume_spike_ratio": round(corr.volume_spike_ratio, 2),
                "price_volatility": round(corr.price_volatility, 2),
                "correlation_strength": corr.correlation_strength,
                "market_impact_score": round(corr.market_impact_score, 1),
                "confidence_level": round(corr.confidence_level, 2),
                "days_before_filing": corr.days_before_filing,
                "days_after_filing": corr.days_after_filing,
                "sector_impact": corr.sector_impact
            }
            for corr in correlations
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing filing correlations for {ticker}: {str(e)}"
        ) from e

@router.get("/summary/{ticker}")
async def get_correlation_summary(
    ticker: str,
    days_lookback: int = Query(30, ge=7, le=90),
    correlation_service: FilingCorrelationService = Depends(_get_correlation_service),  # noqa: B008
    user_context: dict = Depends(get_current_user_context)  # noqa: B008
) -> dict:
    """
    Get summary statistics for filing correlations
    """
    try:
        correlations = await correlation_service.analyze_filing_correlations(
            ticker=ticker.upper(),
            days_lookback=days_lookback,
            min_price_change=0.0  # Include all for summary
        )
        
        if not correlations:
            return {
                "ticker": ticker.upper(),
                "total_filings": 0,
                "strong_correlations": 0,
                "moderate_correlations": 0,
                "weak_correlations": 0,
                "avg_price_impact": 0.0,
                "avg_volume_spike": 0.0,
                "high_impact_forms": []
            }
        
        # Calculate summary statistics
        strong_correlations = len([c for c in correlations if c.correlation_strength == 'strong'])
        moderate_correlations = len(
            [c for c in correlations if c.correlation_strength == 'moderate']
        )
        weak_correlations = len([c for c in correlations if c.correlation_strength == 'weak'])
        
        avg_price_impact = (
            sum(abs(c.price_change_percent) for c in correlations) / len(correlations)
        )
        avg_volume_spike = sum(c.volume_spike_ratio for c in correlations) / len(correlations)
        
        # Get high impact form types
        high_impact_forms = list(set(
            c.form_type for c in correlations 
            if c.market_impact_score > 50
        ))
        
        return {
            "ticker": ticker.upper(),
            "total_filings": len(correlations),
            "strong_correlations": strong_correlations,
            "moderate_correlations": moderate_correlations,
            "weak_correlations": weak_correlations,
            "avg_price_impact": round(avg_price_impact, 2),
            "avg_volume_spike": round(avg_volume_spike, 2),
            "high_impact_forms": high_impact_forms,
            "analysis_period_days": days_lookback
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating correlation summary for {ticker}: {str(e)}"
        ) from e
