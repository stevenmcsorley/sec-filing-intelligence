"""HTTP client and feed parsing logic for SEC EDGAR Atom feeds."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

import httpx

from .models import FilingFeedEntry

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
_ACCESSION_PATTERN = re.compile(r"accession-number=([0-9A-Za-z\-]+)")
_CIK_PATTERN = re.compile(r"/data/(\d{1,10})/")


class EdgarFeedClient:
    """Fetch and normalize EDGAR Atom feeds."""

    def __init__(self, base_headers: dict[str, str]) -> None:
        self._base_headers = base_headers
        self._client: httpx.AsyncClient | None = None

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        self._client = httpx.AsyncClient(headers=self._base_headers, timeout=20.0)
        try:
            yield
        finally:
            await self._client.aclose()
            self._client = None

    async def fetch_feed(self, url: str, *, company: bool = False) -> list[FilingFeedEntry]:
        """Fetch and parse a feed URL into normalized entries."""
        if self._client is None:
            raise RuntimeError("EdgarFeedClient must be used within lifespan()")

        response = await self._client.get(url)
        response.raise_for_status()
        if company:
            return self.parse_company_feed(response.text)
        return list(self._parse_feed(response.text))

    def _parse_feed(self, payload: str) -> Iterable[FilingFeedEntry]:
        root = ET.fromstring(payload)
        for entry in root.findall("atom:entry", ATOM_NS):
            parsed = self._parse_global_entry(entry)
            if parsed:
                yield parsed

    def _parse_global_entry(self, entry: ET.Element) -> FilingFeedEntry | None:
        accession_number = _extract_accession(entry)
        if not accession_number:
            return None

        form_type = _attr(
            entry.find("atom:category", ATOM_NS),
            "term",
            default="UNKNOWN",
        ) or "UNKNOWN"
        filing_href = _attr(entry.find("atom:link", ATOM_NS), "href", default="")
        if not filing_href:
            return None
        updated_text = _text(entry.find("atom:updated", ATOM_NS))
        filed_at = _parse_datetime(updated_text) or datetime.now(UTC)
        cik = _derive_cik(filing_href) or _derive_cik_from_title(
            _text(entry.find("atom:title", ATOM_NS))
        )
        if cik is None:
            return None

        extra = {
            "summary": _text(entry.find("atom:summary", ATOM_NS)),
            "title": _text(entry.find("atom:title", ATOM_NS)),
        }

        return FilingFeedEntry(
            accession_number=accession_number,
            cik=cik,
            form_type=form_type,
            filing_href=filing_href,
            filed_at=filed_at,
            extra=extra,
        )

    def parse_company_feed(self, payload: str) -> list[FilingFeedEntry]:
        """Parse a company-level feed (already fetched) into entries."""
        root = ET.fromstring(payload)
        entries: list[FilingFeedEntry] = []
        for entry in root.findall("atom:entry", ATOM_NS):
            parsed = self._parse_company_entry(entry)
            if parsed:
                entries.append(parsed)
        return entries

    def _parse_company_entry(self, entry: ET.Element) -> FilingFeedEntry | None:
        content_node = entry.find("atom:content", ATOM_NS)
        if content_node is None:
            return None

        # Company feeds embed child elements inside the <content> element rather than
        # providing pure text. Treat the content node as the parent and query children
        # directly to avoid brittle string parsing.
        def from_content(tag: str) -> str:
            for node in content_node.iter():
                local_name = node.tag.split("}")[-1]
                if local_name == tag and node.text:
                    return node.text.strip()
            return ""

        accession_number = from_content("accession-number")
        if not accession_number:
            return None

        cik = from_content("cik")
        if not cik:
            cik = _derive_cik(_attr(entry.find("atom:link", ATOM_NS), "href", default="")) or ""

        form_type = from_content("filing-type") or _attr(
            entry.find("atom:category", ATOM_NS), "term", default="UNKNOWN"
        ) or "UNKNOWN"
        filing_href = from_content("filing-href") or _attr(
            entry.find("atom:link", ATOM_NS), "href", default=""
        )
        if not filing_href:
            return None
        filed_at = _parse_datetime(from_content("filing-date"))
        if filed_at is None:
            filed_at = _parse_datetime(_text(entry.find("atom:updated", ATOM_NS)))
        if filed_at is None:
            filed_at = datetime.now(UTC)

        extra = {
            "summary": _text(entry.find("atom:summary", ATOM_NS)),
            "title": _text(entry.find("atom:title", ATOM_NS)),
        }

        return FilingFeedEntry(
            accession_number=accession_number,
            cik=cik or "",
            form_type=form_type,
            filing_href=filing_href,
            filed_at=filed_at,
            extra=extra,
        )


def _extract_accession(entry: ET.Element) -> str | None:
    id_text = _text(entry.find("atom:id", ATOM_NS))
    if not id_text:
        return None
    if match := _ACCESSION_PATTERN.search(id_text):
        return match.group(1)
    return None


def _derive_cik(href: str | None) -> str | None:
    if not href:
        return None
    if match := _CIK_PATTERN.search(href):
        return match.group(1)
    return None


_TITLE_CIK_PATTERN = re.compile(r"\((\d{5,10})\)")


def _derive_cik_from_title(title: str | None) -> str | None:
    if not title:
        return None
    if match := _TITLE_CIK_PATTERN.search(title):
        return match.group(1)
    return None


def _attr(element: ET.Element | None, name: str, default: str | None = None) -> str | None:
    if element is None:
        return default
    return element.attrib.get(name, default)


def _text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        # fromisoformat supports timezone offsets in Python 3.11+
        return datetime.fromisoformat(value)
    except ValueError:
        return None
