"""Datamodels used by the EDGAR ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class FilingFeedEntry:
    """Normalized representation of a filing entry from EDGAR feeds."""

    accession_number: str
    cik: str
    form_type: str
    filing_href: str
    filed_at: datetime
    extra: dict[str, Any] | None = None


@dataclass(slots=True)
class DownloadTask:
    """Payload published to the ingestion queue for download workers."""

    accession_number: str
    cik: str
    form_type: str
    filing_href: str
    filed_at: datetime
    ticker: str | None = None
    summary: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serializable payload."""
        return {
            "accession_number": self.accession_number,
            "cik": self.cik,
            "form_type": self.form_type,
            "filing_href": self.filing_href,
            "filed_at": self.filed_at.isoformat(),
            "ticker": self.ticker,
            "summary": self.summary,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> DownloadTask:
        """Hydrate a task from a queue payload."""
        filed_at_raw = payload.get("filed_at")
        if isinstance(filed_at_raw, str):
            filed_at = datetime.fromisoformat(filed_at_raw)
        else:
            raise ValueError("DownloadTask payload missing filed_at")

        return cls(
            accession_number=payload["accession_number"],
            cik=payload["cik"],
            form_type=payload.get("form_type", "UNKNOWN"),
            filing_href=payload["filing_href"],
            filed_at=filed_at,
            ticker=payload.get("ticker"),
            summary=payload.get("summary"),
        )


@dataclass(slots=True)
class ParseTask:
    """Payload directing parser workers to process a filing."""

    accession_number: str

    def to_payload(self) -> dict[str, str]:
        return {"accession_number": self.accession_number}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ParseTask:
        return cls(accession_number=payload["accession_number"])
