"""CIK to ticker resolution service."""

from __future__ import annotations

import logging

import httpx

LOGGER = logging.getLogger(__name__)


class TickerLookupService:
    """Service for resolving CIKs to stock tickers using SEC data."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http = http_client

    async def get_ticker_for_cik(self, cik: str) -> str | None:
        """Get ticker for a CIK using SEC submissions API."""
        LOGGER.info(f"Looking up ticker for CIK: {cik}")
        
        # Normalize CIK to 10 digits with leading zeros
        normalized_cik = cik.zfill(10)
        
        try:
            client = self._http or httpx.AsyncClient(timeout=30.0)
            should_close = self._http is None
            
            if should_close:
                async with client:
                    LOGGER.info(
                        f"Making HTTP request to SEC submissions API for CIK {normalized_cik}"
                    )
                    response = await client.get(
                        f"https://data.sec.gov/submissions/CIK{normalized_cik}.json",
                        headers={
                            "User-Agent": "SEC Filing Intelligence/1.0 (test@example.com)",
                            "Accept": "application/json",
                        }
                    )
                    LOGGER.info(f"SEC API response status: {response.status_code}")
                    response.raise_for_status()
                    data = response.json()
            else:
                LOGGER.info(f"Making HTTP request to SEC submissions API for CIK {normalized_cik}")
                response = await client.get(
                    f"https://data.sec.gov/submissions/CIK{normalized_cik}.json",
                    headers={
                        "User-Agent": "SEC Filing Intelligence/1.0 (test@example.com)",
                        "Accept": "application/json",
                    }
                )
                LOGGER.info(f"SEC API response status: {response.status_code}")
                response.raise_for_status()
                data = response.json()

            # Extract ticker from the response
            tickers = data.get("tickers", [])
            if tickers and len(tickers) > 0:
                ticker = tickers[0].upper()
                LOGGER.info(f"Found ticker for CIK {cik}: {ticker}")
                return ticker
            
            LOGGER.info(f"No ticker found for CIK {cik}")
            return None
            
        except Exception as exc:
            LOGGER.error(f"Failed to get ticker for CIK {cik}: {exc}")
            return None
            
    async def get_company_info_for_cik(self, cik: str) -> dict[str, str | None] | None:
        """Get company name and ticker for a CIK using SEC submissions API."""
        # Normalize CIK to 10 digits with leading zeros
        normalized_cik = cik.zfill(10)
        
        try:
            client = self._http or httpx.AsyncClient(timeout=30.0)
            should_close = self._http is None
            
            if should_close:
                async with client:
                    LOGGER.info(
                        f"Making HTTP request to SEC submissions API for CIK {normalized_cik}"
                    )
                    response = await client.get(
                        f"https://data.sec.gov/submissions/CIK{normalized_cik}.json",
                        headers={
                            "User-Agent": "SEC Filing Intelligence/1.0 (test@example.com)",
                            "Accept": "application/json",
                        }
                    )
                    LOGGER.info(f"SEC API response status: {response.status_code}")
                    response.raise_for_status()
                    data = response.json()
            else:
                LOGGER.info(f"Making HTTP request to SEC submissions API for CIK {normalized_cik}")
                response = await client.get(
                    f"https://data.sec.gov/submissions/CIK{normalized_cik}.json",
                    headers={
                        "User-Agent": "SEC Filing Intelligence/1.0 (test@example.com)",
                        "Accept": "application/json",
                    }
                )
                LOGGER.info(f"SEC API response status: {response.status_code}")
                response.raise_for_status()
                data = response.json()

            # Extract company info
            company_name = data.get("name")
            tickers = data.get("tickers", [])
            ticker = tickers[0] if tickers else None
            
            if company_name:
                result = {
                    "company_name": company_name,
                    "ticker": ticker.upper() if ticker else None,
                    "cik": normalized_cik
                }
                LOGGER.info(f"Found company info for CIK {cik}: {result}")
                return result
            
            LOGGER.info(f"No company info found for CIK {cik}")
            return None

        except Exception as exc:
            LOGGER.error(f"Failed to get company info for CIK {cik}: {exc}")
            return None