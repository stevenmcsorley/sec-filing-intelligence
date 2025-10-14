"""CIK to ticker resolution service with enhanced company name matching and caching."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
from redis.asyncio import Redis

LOGGER = logging.getLogger(__name__)


@dataclass
class CompanyInfo:
    """Structured company information."""
    cik: str
    name: str
    ticker: str | None
    normalized_name: str
    confidence: float
    last_updated: datetime


class CompanyNameNormalizer:
    """Normalizes company names for better matching."""
    
    # Common company suffixes and their variations
    COMPANY_SUFFIXES = {
        'corp', 'corporation', 'inc', 'incorporated', 'llc', 'ltd', 'limited',
        'co', 'company', 'grp', 'group', 'intl', 'international', 'sys', 'systems',
        'tech', 'technology', 'mfg', 'manufacturing', 'holdings', 'hold', 'hldg'
    }
    
    # Common abbreviations
    ABBREVIATIONS = {
        'intl': 'international',
        'sys': 'systems', 
        'tech': 'technology',
        'mfg': 'manufacturing',
        'grp': 'group',
        'corp': 'corporation',
        'inc': 'incorporated',
        'ltd': 'limited',
        'co': 'company'
    }
    
    @classmethod
    def normalize_name(cls, name: str) -> str:
        """Normalize a company name for comparison."""
        if not name:
            return ""
            
        # Convert to lowercase and strip whitespace
        normalized = name.lower().strip()
        
        # Remove common punctuation
        normalized = re.sub(r'[.,\-&]', ' ', normalized)
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove common suffixes
        words = normalized.split()
        filtered_words = []
        
        for word in words:
            # Skip common suffixes
            if word not in cls.COMPANY_SUFFIXES:
                # Expand abbreviations
                expanded = cls.ABBREVIATIONS.get(word, word)
                filtered_words.append(expanded)
        
        return ' '.join(filtered_words)
    
    @classmethod
    def calculate_similarity(cls, name1: str, name2: str) -> float:
        """Calculate similarity between two normalized company names."""
        norm1 = cls.normalize_name(name1)
        norm2 = cls.normalize_name(name2)
        
        if not norm1 or not norm2:
            return 0.0
            
        # Exact match
        if norm1 == norm2:
            return 1.0
            
        # Check if one contains the other (partial match)
        if norm1 in norm2 or norm2 in norm1:
            return 0.8
            
        # Word overlap
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            return 0.0
            
        overlap = len(words1.intersection(words2))
        total = len(words1.union(words2))
        
        return overlap / total if total > 0 else 0.0


class TickerLookupService:
    """Enhanced service for resolving CIKs to stock tickers with caching and smart matching."""

    def __init__(
        self, 
        http_client: httpx.AsyncClient | None = None,
        redis_client: Redis | None = None,
        cache_ttl_hours: int = 24
    ) -> None:
        self._http = http_client
        self._redis = redis_client
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self._normalizer = CompanyNameNormalizer()

    async def get_ticker_for_cik(self, cik: str) -> str | None:
        """Get ticker for a CIK using SEC submissions API with caching."""
        normalized_cik = cik.zfill(10)
        
        # Check cache first
        if self._redis:
            cached_ticker = await self._get_cached_ticker(normalized_cik)
            if cached_ticker:
                LOGGER.debug(f"Found cached ticker for CIK {cik}: {cached_ticker}")
                return cached_ticker
        
        # Fetch from SEC API
        company_info = await self._fetch_company_info_from_sec(normalized_cik)
        if company_info and company_info.ticker:
            # Cache the result
            if self._redis:
                await self._cache_ticker(normalized_cik, company_info.ticker)
            
            LOGGER.info(f"Found ticker for CIK {cik}: {company_info.ticker}")
            return company_info.ticker
        
        LOGGER.info(f"No ticker found for CIK {cik}")
        return None

    async def get_company_info_for_cik(self, cik: str) -> dict[str, str | None] | None:
        """Get company name and ticker for a CIK using SEC submissions API with caching."""
        normalized_cik = cik.zfill(10)
        
        # Check cache first
        if self._redis:
            cached_info = await self._get_cached_company_info(normalized_cik)
            if cached_info:
                LOGGER.debug(f"Found cached company info for CIK {cik}")
                return {
                    "company_name": cached_info.name,
                    "ticker": cached_info.ticker,
                    "cik": normalized_cik
                }
        
        # Fetch from SEC API
        company_info = await self._fetch_company_info_from_sec(normalized_cik)
        if company_info:
            # Cache the result
            if self._redis:
                await self._cache_company_info(normalized_cik, company_info)
            
            result = {
                "company_name": company_info.name,
                "ticker": company_info.ticker,
                "cik": normalized_cik
            }
            LOGGER.info(f"Found company info for CIK {cik}: {result}")
            return result
        
        LOGGER.info(f"No company info found for CIK {cik}")
        return None

    async def find_company_by_name(self, company_name: str) -> CompanyInfo | None:
        """Find company by name using fuzzy matching."""
        if not company_name or not company_name.strip():
            return None
            
        normalized_search = self._normalizer.normalize_name(company_name)
        LOGGER.info(f"Searching for company: '{company_name}' (normalized: '{normalized_search}')")
        
        # This would ideally use a company database or search API
        # For now, we'll implement a basic search that could be enhanced
        # with a proper company database lookup
        
        # Check if we have cached companies with similar names
        if self._redis:
            cached_companies = await self._search_cached_companies(normalized_search)
            if cached_companies:
                best_match = max(cached_companies, key=lambda c: c.confidence)
                if best_match.confidence > 0.7:  # High confidence threshold
                    LOGGER.info(
                    f"Found cached company match: {best_match.name} "
                    f"(confidence: {best_match.confidence})"
                )
                    return best_match
        
        # If no cached match, we could implement a broader search here
        # This would require integrating with a company database or search service
        LOGGER.info(f"No company match found for: '{company_name}'")
        return None

    async def _fetch_company_info_from_sec(self, normalized_cik: str) -> CompanyInfo | None:
        """Fetch company information from SEC API."""
        try:
            client = self._http or httpx.AsyncClient(timeout=30.0)
            should_close = self._http is None
            
            if should_close:
                async with client:
                    response = await client.get(
                        f"https://data.sec.gov/submissions/CIK{normalized_cik}.json",
                        headers={
                            "User-Agent": "SEC Filing Intelligence/1.0 (support@sec-intel.local)",
                            "Accept": "application/json",
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
            else:
                response = await client.get(
                    f"https://data.sec.gov/submissions/CIK{normalized_cik}.json",
                    headers={
                        "User-Agent": "SEC Filing Intelligence/1.0 (support@sec-intel.local)",
                        "Accept": "application/json",
                    }
                )
                response.raise_for_status()
                data = response.json()

            # Extract company info
            company_name = data.get("name")
            tickers = data.get("tickers", [])
            ticker = tickers[0] if tickers else None
            
            if company_name:
                normalized_name = self._normalizer.normalize_name(str(company_name))
                return CompanyInfo(
                    cik=normalized_cik,
                    name=str(company_name),
                    ticker=ticker.upper() if ticker else None,
                    normalized_name=normalized_name,
                    confidence=1.0,  # High confidence for direct SEC data
                    last_updated=datetime.now()
                )
            
            return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                LOGGER.warning(f"CIK {normalized_cik} not found in SEC database")
            else:
                LOGGER.error(f"HTTP error fetching company info for CIK {normalized_cik}: {e}")
            return None
        except Exception as exc:
            LOGGER.error(f"Failed to fetch company info for CIK {normalized_cik}: {exc}")
            return None

    async def _get_cached_ticker(self, normalized_cik: str) -> str | None:
        """Get cached ticker from Redis."""
        if not self._redis:
            return None
        try:
            cached = await self._redis.get(f"ticker:{normalized_cik}")
            return cached.decode() if cached else None
        except Exception as e:
            LOGGER.warning(f"Failed to get cached ticker for CIK {normalized_cik}: {e}")
            return None

    async def _cache_ticker(self, normalized_cik: str, ticker: str) -> None:
        """Cache ticker in Redis."""
        if not self._redis:
            return
        try:
            await self._redis.setex(
                f"ticker:{normalized_cik}",
                int(self._cache_ttl.total_seconds()),
                ticker
            )
        except Exception as e:
            LOGGER.warning(f"Failed to cache ticker for CIK {normalized_cik}: {e}")

    async def _get_cached_company_info(self, normalized_cik: str) -> CompanyInfo | None:
        """Get cached company info from Redis."""
        if not self._redis:
            return None
        try:
            cached = await self._redis.get(f"company:{normalized_cik}")
            if cached:
                import json
                data = json.loads(cached.decode())
                return CompanyInfo(
                    cik=data["cik"],
                    name=data["name"],
                    ticker=data["ticker"],
                    normalized_name=data["normalized_name"],
                    confidence=data["confidence"],
                    last_updated=datetime.fromisoformat(data["last_updated"])
                )
            return None
        except Exception as e:
            LOGGER.warning(f"Failed to get cached company info for CIK {normalized_cik}: {e}")
            return None

    async def _cache_company_info(self, normalized_cik: str, company_info: CompanyInfo) -> None:
        """Cache company info in Redis."""
        if not self._redis:
            return
        try:
            import json
            data = {
                "cik": company_info.cik,
                "name": company_info.name,
                "ticker": company_info.ticker,
                "normalized_name": company_info.normalized_name,
                "confidence": company_info.confidence,
                "last_updated": company_info.last_updated.isoformat()
            }
            await self._redis.setex(
                f"company:{normalized_cik}",
                int(self._cache_ttl.total_seconds()),
                json.dumps(data)
            )
        except Exception as e:
            LOGGER.warning(f"Failed to cache company info for CIK {normalized_cik}: {e}")

    async def _search_cached_companies(self, normalized_search: str) -> list[CompanyInfo]:
        """Search cached companies by normalized name."""
        if not self._redis:
            return []
        
        try:
            # This is a simplified implementation
            # In a real system, you'd use Redis search or a proper database
            # For now, we'll return an empty list
            return []
        except Exception as e:
            LOGGER.warning(f"Failed to search cached companies: {e}")
            return []