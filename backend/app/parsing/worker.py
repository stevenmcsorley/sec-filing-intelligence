"""Parser worker that reads filings and emits sections."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from typing import Protocol

import pdfminer.high_level
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ingestion.models import ParseTask
from app.models.filing import Filing, FilingBlob, FilingSection, FilingStatus

from .metrics import PARSER_ERRORS_TOTAL, PARSER_LATENCY_SECONDS, PARSER_SECTIONS_TOTAL
from .queue import ParseQueue
from .sectionizer import Section, extract_sections, html_to_text

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ParserOptions:
    max_retries: int
    backoff_seconds: float


class ArtifactFetcher(Protocol):
    async def fetch(self, location: str) -> bytes:
        ...


class ParserWorker:
    def __init__(
        self,
        *,
        name: str,
        queue: ParseQueue,
        session_factory: async_sessionmaker[AsyncSession],
        fetcher: ArtifactFetcher,
        options: ParserOptions,
    ) -> None:
        self._name = name
        self._queue = queue
        self._session_factory = session_factory
        self._fetcher = fetcher
        self._options = options

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            task = await self._queue.pop(timeout=5)
            if task is None:
                continue
            await self._handle_task(task)

    async def _handle_task(self, task: ParseTask) -> None:
        start = datetime.now(UTC)
        try:
            sections = await self._parse_task(task)
        except Exception:
            LOGGER.exception("Failed to parse filing", extra={"accession": task.accession_number})
            PARSER_ERRORS_TOTAL.labels("parse").inc()
            await self._mark_failed(task)
            return

        async with self._session_factory() as session:
            async with session.begin():
                stmt = select(Filing).where(Filing.accession_number == task.accession_number)
                filing = (await session.execute(stmt)).scalar_one()
                await session.execute(
                    delete(FilingSection).where(FilingSection.filing_id == filing.id)
                )
                for ordinal, section in enumerate(sections, start=1):
                    session.add(
                        FilingSection(
                            filing_id=filing.id,
                            title=section.title,
                            ordinal=ordinal,
                            content=section.content,
                        )
                    )
                filing.status = FilingStatus.PARSED.value
            PARSER_SECTIONS_TOTAL.inc(len(sections))
        PARSER_LATENCY_SECONDS.observe((datetime.now(UTC) - start).total_seconds())

    async def _mark_failed(self, task: ParseTask) -> None:
        async with self._session_factory() as session:
            stmt = select(Filing).where(Filing.accession_number == task.accession_number)
            filing = (await session.execute(stmt)).scalar_one_or_none()
            if filing is None:
                return
            filing.status = FilingStatus.FAILED.value
            await session.commit()

    async def _parse_task(self, task: ParseTask) -> list[Section]:
        async with self._session_factory() as session:
            stmt = select(Filing).where(Filing.accession_number == task.accession_number)
            filing = (await session.execute(stmt)).scalar_one()
            blob_stmt = select(FilingBlob).where(FilingBlob.filing_id == filing.id)
            blobs = (await session.execute(blob_stmt)).scalars().all()

        raw_blob = _select_blob(blobs, "raw")
        if raw_blob is not None:
            data = await self._fetcher.fetch(raw_blob.location)
            text = await self._extract_text(raw_blob, data)
            return extract_sections(text)

        index_blob = _select_blob(blobs, "index")
        if index_blob is not None:
            data = await self._fetcher.fetch(index_blob.location)
            text = html_to_text(data.decode("utf-8", errors="ignore"))
            return extract_sections(text)

        raise RuntimeError("No artifacts available for parsing")

    async def _extract_text(self, blob: FilingBlob, data: bytes) -> str:
        if blob.content_type and "pdf" in blob.content_type.lower():
            return await asyncio.to_thread(_pdf_to_text, data)
        text = data.decode("utf-8", errors="ignore")
        if blob.content_type and "html" in blob.content_type.lower():
            return html_to_text(text)
        return text


def _select_blob(blobs: Iterable[FilingBlob], kind: str) -> FilingBlob | None:
    for blob in blobs:
        if blob.kind == kind:
            return blob
    return None


def _pdf_to_text(data: bytes) -> str:
    buffer = BytesIO(data)
    try:
        text = pdfminer.high_level.extract_text(buffer)
    finally:
        buffer.close()
    return text
