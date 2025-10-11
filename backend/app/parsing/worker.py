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

from app.ingestion.backpressure import QueueBackpressure
from app.ingestion.models import ParseTask
from app.models.filing import Filing, FilingBlob, FilingSection, FilingStatus
from app.orchestration.metrics import CHUNK_PLANNER_CHUNKS_TOTAL, CHUNK_PLANNER_LATENCY_SECONDS
from app.orchestration.planner import ChunkPlanner, ChunkPlannerOptions, PlannerSection
from app.orchestration.queue import ChunkQueue

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
        chunk_queue: ChunkQueue | None = None,
        chunk_planner: ChunkPlanner | None = None,
        chunk_backpressure: QueueBackpressure | None = None,
        chunk_options: ChunkPlannerOptions | None = None,
    ) -> None:
        self._name = name
        self._queue = queue
        self._session_factory = session_factory
        self._fetcher = fetcher
        self._options = options
        self._chunk_queue = chunk_queue
        self._chunk_planner = chunk_planner or (
            ChunkPlanner(chunk_options) if chunk_queue else None
        )
        self._chunk_backpressure = chunk_backpressure

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            task = await self._queue.pop(timeout=5)
            if task is None:
                continue
            try:
                await self._handle_task(task)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception(
                    "Parser worker crashed",
                    extra={"worker": self._name, "accession": task.accession_number},
                )
                PARSER_ERRORS_TOTAL.labels("worker").inc()
                try:
                    await self._mark_failed(task)
                except Exception:
                    LOGGER.exception(
                        "Failed to mark filing as failed after crash",
                        extra={"worker": self._name, "accession": task.accession_number},
                    )

    async def _handle_task(self, task: ParseTask) -> None:
        start = datetime.now(UTC)
        try:
            sections = await self._parse_task(task)
        except Exception:
            LOGGER.exception("Failed to parse filing", extra={"accession": task.accession_number})
            PARSER_ERRORS_TOTAL.labels("parse").inc()
            await self._mark_failed(task)
            return

        planner_sections: list[PlannerSection] = []
        form_type: str | None = None

        async with self._session_factory() as session:
            async with session.begin():
                stmt = select(Filing).where(Filing.accession_number == task.accession_number)
                filing = (await session.execute(stmt)).scalar_one()
                form_type = filing.form_type
                await session.execute(
                    delete(FilingSection).where(FilingSection.filing_id == filing.id)
                )
                for ordinal, section in enumerate(sections, start=1):
                    planner_sections.append(
                        PlannerSection(
                            ordinal=ordinal,
                            title=section.title,
                            content=section.content,
                        )
                    )
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

        if self._chunk_queue and self._chunk_planner and planner_sections:
            if self._chunk_backpressure is not None:
                await self._chunk_backpressure.wait_if_needed()
            plan_start = datetime.now(UTC)
            jobs = self._chunk_planner.plan(task.accession_number, planner_sections)
            CHUNK_PLANNER_LATENCY_SECONDS.observe(
                (datetime.now(UTC) - plan_start).total_seconds()
            )
            if form_type is None:
                form_type = "unknown"
            CHUNK_PLANNER_CHUNKS_TOTAL.labels(form_type).inc(len(jobs))
            for job in jobs:
                await self._chunk_queue.push(job)
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
