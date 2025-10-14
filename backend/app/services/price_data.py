"""Price data service for fetching stock prices from Yahoo Finance."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx
from redis.asyncio import Redis


class PriceDataService:
    """Service for fetching and caching stock price data from Yahoo Finance."""
    
    def __init__(self, redis_client: Redis | None = None) -> None:
        self._redis = redis_client
        self._cache_ttl = 300  # 5 minutes for current data
        self._historical_cache_ttl = 3600  # 1 hour for historical data
        
    async def get_current_price(self, ticker: str) -> dict[str, Any] | None:
        """Get current stock price and basic metrics from Yahoo Finance."""
        cache_key = f"price:current:{ticker}"
        
        # Try cache first
        if self._redis:
            cached_data = await self._get_cached_data(cache_key)
            if cached_data:
                return cached_data
        
        try:
            # Yahoo Finance API endpoint
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            params = {
                "interval": "1d",
                "range": "1d",
                "includePrePost": "false"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            # Parse Yahoo Finance response
            chart_data = data.get("chart", {}).get("result", [])
            if not chart_data:
                return None
            
            result = chart_data[0]
            meta = result.get("meta", {})
            quote = result.get("indicators", {}).get("quote", [{}])[0]
            
            # Get the latest price data
            timestamps = result.get("timestamp", [])
            if not timestamps:
                return None
            
            latest_idx = -1
            current_price = quote.get("close", [None])[latest_idx]
            
            if current_price is None:
                return None
            
            price_data = {
                "ticker": ticker.upper(),
                "price": round(current_price, 2),
                "change": round(
                    quote.get("close", [0])[latest_idx] - meta.get("previousClose", 0), 
                    2
                ),
                "change_percent": round(
                    ((quote.get("close", [0])[latest_idx] - meta.get("previousClose", 0)) / 
                     meta.get("previousClose", 1)) * 100, 
                    2
                ),
                "volume": quote.get("volume", [0])[latest_idx] or 0,
                "high": round(quote.get("high", [0])[latest_idx] or 0, 2),
                "low": round(quote.get("low", [0])[latest_idx] or 0, 2),
                "open": round(quote.get("open", [0])[latest_idx] or 0, 2),
                "previous_close": round(meta.get("previousClose", 0), 2),
                "market_cap": meta.get("marketCap"),
                "timestamp": datetime.now(UTC).isoformat()
            }
            
            # Cache the result
            if self._redis:
                await self._cache_data(cache_key, price_data, self._cache_ttl)
            
            return price_data
            
        except Exception as e:
            print(f"Error fetching current price for {ticker}: {e}")
            return None
    
    async def get_historical_prices(
        self, 
        ticker: str, 
        days: int = 30
    ) -> list[dict[str, Any]] | None:
        """Get historical price data for the last N days from Yahoo Finance."""
        cache_key = f"price:historical:{ticker}:{days}"
        
        # Try cache first
        if self._redis:
            cached_data = await self._get_cached_data(cache_key)
            if cached_data:
                return cached_data
        
        try:
            # Yahoo Finance API endpoint
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            params = {
                "interval": "1d",
                "range": f"{days}d",
                "includePrePost": "false"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            # Parse Yahoo Finance response
            chart_data = data.get("chart", {}).get("result", [])
            if not chart_data:
                return None
            
            result = chart_data[0]
            timestamps = result.get("timestamp", [])
            quote = result.get("indicators", {}).get("quote", [{}])[0]
            
            # Convert to list
            historical_data = []
            for i, timestamp in enumerate(timestamps):
                if i < len(quote.get("close", [])):
                    historical_data.append({
                        "date": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d"),
                        "open": round(quote.get("open", [0])[i] or 0, 2),
                        "high": round(quote.get("high", [0])[i] or 0, 2),
                        "low": round(quote.get("low", [0])[i] or 0, 2),
                        "close": round(quote.get("close", [0])[i] or 0, 2),
                        "volume": quote.get("volume", [0])[i] or 0
                    })
            
            # Cache the result
            if self._redis:
                await self._cache_data(cache_key, historical_data, self._historical_cache_ttl)
            
            return historical_data
            
        except Exception as e:
            print(f"Error fetching historical prices for {ticker}: {e}")
            return None
    
    async def get_company_overview(self, ticker: str) -> dict[str, Any] | None:
        """Get company overview information from Yahoo Finance."""
        cache_key = f"price:overview:{ticker}"
        
        # Try cache first
        if self._redis:
            cached_data = await self._get_cached_data(cache_key)
            if cached_data:
                return cached_data
        
        try:
            # Yahoo Finance API endpoint for company info
            url = "https://query1.finance.yahoo.com/v1/finance/search"
            params = {"q": ticker}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            # Parse search results
            quotes = data.get("quotes", [])
            if not quotes:
                return None
            
            quote = quotes[0]
            overview_data = {
                "ticker": quote.get("symbol", ticker.upper()),
                "name": quote.get("longname") or quote.get("shortname"),
                "sector": quote.get("sector"),
                "industry": quote.get("industry"),
                "market_cap": quote.get("marketCap"),
                "exchange": quote.get("exchange"),
                "currency": quote.get("currency"),
                "timezone": quote.get("timezone")
            }
            
            # Cache the result
            if self._redis:
                await self._cache_data(cache_key, overview_data, self._historical_cache_ttl)
            
            return overview_data
            
        except Exception as e:
            print(f"Error fetching company overview for {ticker}: {e}")
            return None
    
    async def _get_cached_data(self, cache_key: str) -> Any | None:
        """Get data from Redis cache."""
        if not self._redis:
            return None
        
        try:
            cached = await self._redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            print(f"Error reading from cache {cache_key}: {e}")
        
        return None
    
    async def _cache_data(self, cache_key: str, data: Any, ttl: int) -> None:
        """Cache data in Redis."""
        if not self._redis:
            return
        
        try:
            await self._redis.setex(
                cache_key, 
                ttl, 
                json.dumps(data, default=str)
            )
        except Exception as e:
            print(f"Error caching data {cache_key}: {e}")
    
    async def close(self) -> None:
        """Close Redis connection if needed."""
        if self._redis:
            await self._redis.close()
