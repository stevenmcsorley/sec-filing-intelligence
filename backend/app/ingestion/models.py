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

    def to_payload(self) -> dict[str, str]:
        """Return a JSON-serializable payload."""
        return {
            "accession_number": self.accession_number,
            "cik": self.cik,
            "form_type": self.form_type,
            "filing_href": self.filing_href,
        }
