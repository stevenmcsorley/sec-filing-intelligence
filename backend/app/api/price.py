"""Price data API endpoints."""

# ruff: noqa: B008
from __future__ import annotations

from typing import Any

from app.auth.dependencies import get_current_user_context
from app.auth.models import UserContext
from app.config import get_settings
from app.services.price_data import PriceDataService
from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis

router = APIRouter(prefix="/api/v1/price", tags=["price"])


def _get_price_service() -> PriceDataService:
    """Get price data service with Redis caching."""
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url)
    return PriceDataService(redis_client=redis_client)


@router.get("/current/{ticker}")
async def get_current_price(
    ticker: str,
    price_service: PriceDataService = Depends(_get_price_service),
    _: UserContext = Depends(get_current_user_context),
) -> dict[str, Any]:
    """Get current stock price and basic metrics."""
    price_data = await price_service.get_current_price(ticker.upper())
    
    if not price_data:
        raise HTTPException(
            status_code=404, 
            detail=f"Price data not found for ticker {ticker}"
        )
    
    return price_data


@router.get("/historical/{ticker}")
async def get_historical_prices(
    ticker: str,
    days: int = Query(default=30, ge=1, le=365),
    price_service: PriceDataService = Depends(_get_price_service),
    _: UserContext = Depends(get_current_user_context),
) -> dict[str, Any]:
    """Get historical price data for the last N days."""
    historical_data = await price_service.get_historical_prices(ticker.upper(), days)
    
    if not historical_data:
        raise HTTPException(
            status_code=404, 
            detail=f"Historical price data not found for ticker {ticker}"
        )
    
    return {
        "ticker": ticker.upper(),
        "days": days,
        "data": historical_data
    }


@router.get("/overview/{ticker}")
async def get_company_overview(
    ticker: str,
    price_service: PriceDataService = Depends(_get_price_service),
    _: UserContext = Depends(get_current_user_context),
) -> dict[str, Any]:
    """Get company overview information."""
    overview_data = await price_service.get_company_overview(ticker.upper())
    
    if not overview_data:
        raise HTTPException(
            status_code=404, 
            detail=f"Company overview not found for ticker {ticker}"
        )
    
    return overview_data


@router.get("/correlation/{ticker}")
async def get_filing_price_correlation(
    ticker: str,
    days: int = Query(default=30, ge=1, le=365),
    price_service: PriceDataService = Depends(_get_price_service),
    _: UserContext = Depends(get_current_user_context),
) -> dict[str, Any]:
    """Get price correlation analysis with recent filings."""
    # This would integrate with filing data to show correlations
    # For now, return a placeholder structure
    return {
        "ticker": ticker.upper(),
        "analysis_period_days": days,
        "correlation_insights": [
            {
                "filing_date": "2024-10-10",
                "filing_type": "10-K",
                "price_change_percent": 2.5,
                "volume_spike": True,
                "correlation_strength": "moderate"
            }
        ],
        "summary": f"Analysis of {ticker} price movements around recent filings"
    }
