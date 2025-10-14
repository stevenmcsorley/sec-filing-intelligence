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
from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.diff.queue import DiffQueue, DiffTask
from app.ingestion.backpressure import QueueBackpressure
from app.ingestion.models import ParseTask
from app.models.company import Company
from app.models.diff import DiffStatus, FilingDiff, FilingSectionDiff
from app.models.filing import Filing, FilingBlob, FilingSection, FilingStatus
from app.orchestration.metrics import CHUNK_PLANNER_CHUNKS_TOTAL, CHUNK_PLANNER_LATENCY_SECONDS
from app.orchestration.planner import ChunkPlanner, ChunkPlannerOptions, PlannerSection
from app.orchestration.queue import ChunkQueue
from app.sec_utils import extract_issuer_cik, extract_issuer_name
from app.services.ticker_lookup import TickerLookupService

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


@dataclass(slots=True)
class ChunkQueueTarget:
    queue: ChunkQueue
    suffix: str = ""
    backpressure: QueueBackpressure | None = None


class ParserWorker:
    def __init__(
        self,
        *,
        name: str,
        queue: ParseQueue,
        session_factory: async_sessionmaker[AsyncSession],
        fetcher: ArtifactFetcher,
        options: ParserOptions,
        chunk_targets: Iterable[ChunkQueueTarget] | None = None,
        chunk_planner: ChunkPlanner | None = None,
        chunk_options: ChunkPlannerOptions | None = None,
        diff_queue: DiffQueue | None = None,
        diff_backpressure: QueueBackpressure | None = None,
    ) -> None:
        self._name = name
        self._queue = queue
        self._session_factory = session_factory
        self._fetcher = fetcher
        self._options = options
        self._chunk_targets: list[ChunkQueueTarget] = list(chunk_targets or [])
        if not self._chunk_targets and chunk_planner is None:
            self._chunk_planner = None
        else:
            self._chunk_planner = chunk_planner or ChunkPlanner(chunk_options)
        self._diff_queue = diff_queue
        self._diff_backpressure = diff_backpressure

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
        sections: list[Section] = []
        try:
            sections = await self._parse_task(task)
        except Exception:
            LOGGER.exception("Failed to parse filing", extra={"accession": task.accession_number})
            PARSER_ERRORS_TOTAL.labels("parse").inc()
            # Even if parsing fails, try to process Form 4 issuer info from raw content
            await self._try_process_form4_issuer_from_raw(task)
            await self._mark_failed(task)
            return

        planner_sections: list[PlannerSection] = []
        form_type: str | None = None
        filing_id: int | None = None
        company_id: int | None = None
        filed_at: datetime | None = None

        async with self._session_factory() as session:
            async with session.begin():
                stmt = select(Filing).where(Filing.accession_number == task.accession_number)
                filing = (await session.execute(stmt)).scalar_one()
                form_type = filing.form_type
                filing_id = filing.id
                company_id = filing.company_id
                filed_at = filing.filed_at
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
                
                # For Form 4, Form 144, Schedule 13D/A, and Form 3 filings,
                # extract issuer information and update company if needed
                if filing.form_type in ['4', '144', 'SCHEDULE 13D/A', '3']:
                    await self._process_form4_issuer(session, filing, sections)
                
                # For ALL filings, ensure ticker is looked up and updated
                await self._ensure_ticker_lookup(session, filing)
                
                filing.status = FilingStatus.PARSED.value
            PARSER_SECTIONS_TOTAL.inc(len(sections))

        if self._chunk_targets and self._chunk_planner and planner_sections:
            plan_start = datetime.now(UTC)
            jobs = self._chunk_planner.plan(task.accession_number, planner_sections)
            CHUNK_PLANNER_LATENCY_SECONDS.observe(
                (datetime.now(UTC) - plan_start).total_seconds()
            )
            if form_type is None:
                form_type = "unknown"
            CHUNK_PLANNER_CHUNKS_TOTAL.labels(form_type).inc(len(jobs))
            for job in jobs:
                for target in self._chunk_targets:
                    if target.backpressure is not None:
                        await target.backpressure.wait_if_needed()
                    if target.suffix:
                        job_to_push = job.with_job_id(f"{job.job_id}{target.suffix}")
                    else:
                        job_to_push = job
                    await target.queue.push(job_to_push)
        await self._schedule_diff_jobs(
            filing_id=filing_id,
            company_id=company_id,
            form_type=form_type,
            filed_at=filed_at,
            accession_number=task.accession_number,
        )
        PARSER_LATENCY_SECONDS.observe((datetime.now(UTC) - start).total_seconds())

    async def _process_form4_issuer(
        self, session: AsyncSession, filing: Filing, sections: list[Section]
    ) -> None:
        """Process Form 4, Form 144, and Schedule 13D/A filings to extract issuer 
        information and update company records."""
        # Extract issuer CIK and name from filing content
        issuer_cik = None
        issuer_name = None
        
        # First try the raw blob content
        blob_stmt = (
            select(FilingBlob)
            .where(FilingBlob.filing_id == filing.id, FilingBlob.kind == 'raw')
        )
        raw_blob = (await session.execute(blob_stmt)).scalar_one_or_none()
        
        if raw_blob:
            try:
                raw_content = await self._fetcher.fetch(raw_blob.location)
                raw_text = raw_content.decode('utf-8', errors='ignore')
                issuer_cik = extract_issuer_cik(raw_text)
                issuer_name = extract_issuer_name(raw_text)
                if issuer_cik:
                    LOGGER.info(
                        "Extracted issuer CIK from raw filing content",
                        extra={
                            "accession": filing.accession_number,
                            "issuer_cik": issuer_cik,
                            "issuer_name": issuer_name,
                            "original_cik": filing.cik
                        }
                    )
            except Exception as e:
                LOGGER.warning(
                    "Failed to fetch raw blob content",
                    extra={"accession": filing.accession_number, "error": str(e)}
                )
        
        # Fallback to parsed sections if raw blob didn't work
        if not issuer_cik:
            for section in sections:
                issuer_cik = extract_issuer_cik(section.content)
                issuer_name = extract_issuer_name(section.content)
                if issuer_cik:
                    LOGGER.info(
                        "Extracted issuer CIK from parsed sections",
                        extra={
                            "accession": filing.accession_number,
                            "issuer_cik": issuer_cik,
                            "issuer_name": issuer_name,
                            "original_cik": filing.cik
                        }
                    )
                    break
        
        if not issuer_cik:
            LOGGER.warning(
                "Could not extract issuer CIK from Form 4/144/Schedule 13D/A filing",
                extra={"accession": filing.accession_number}
            )
            return
        
        # If issuer CIK is different from filing CIK, we need to update the company association
        if issuer_cik != filing.cik:
            # Check if issuer company already exists
            issuer_company_stmt = select(Company).where(Company.cik == issuer_cik)
            issuer_company = (await session.execute(issuer_company_stmt)).scalar_one_or_none()
            
            if issuer_company is None:
                # Create new company for the issuer
                # Initialize Redis client for caching
                settings = Settings()
                redis_client = Redis.from_url(settings.redis_url)
                ticker_service = TickerLookupService(redis_client=redis_client)
                company_info = await ticker_service.get_company_info_for_cik(issuer_cik)
                
                issuer_company = Company(
                    cik=issuer_cik,
                    name=(
                        issuer_name or
                        company_info.get("company_name", f"Company {issuer_cik}")
                        if company_info else 
                        (issuer_name or f"Company {issuer_cik}")
                    ),
                    ticker=company_info.get("ticker") if company_info else None
                )
                session.add(issuer_company)
                await session.flush()
                
                LOGGER.info(
                    "Created new issuer company",
                    extra={
                        "accession": filing.accession_number,
                        "issuer_cik": issuer_cik,
                        "company_name": issuer_company.name,
                        "ticker": issuer_company.ticker
                    }
                )
            else:
                # Update existing issuer company info if needed
                # Initialize Redis client for caching
                settings = Settings()
                redis_client = Redis.from_url(settings.redis_url)
                ticker_service = TickerLookupService(redis_client=redis_client)
                company_info = await ticker_service.get_company_info_for_cik(issuer_cik)
                
                if company_info:
                    company_name = company_info.get("company_name")
                    ticker = company_info.get("ticker")
                    if (company_name and
                        issuer_company.name.startswith("Company ")):
                        issuer_company.name = company_name
                    if ticker and not issuer_company.ticker:
                        issuer_company.ticker = ticker
                
                LOGGER.info(
                    "Updated existing issuer company",
                    extra={
                        "accession": filing.accession_number,
                        "issuer_cik": issuer_cik,
                        "company_name": issuer_company.name,
                        "ticker": issuer_company.ticker
                    }
                )
            
            # Update filing to point to the correct issuer company
            filing.company_id = issuer_company.id
            filing.cik = issuer_cik
            filing.ticker = issuer_company.ticker
            
            LOGGER.info(
                "Updated filing company association",
                extra={
                    "accession": filing.accession_number,
                    "old_cik": filing.cik,
                    "new_cik": issuer_cik,
                    "company_id": issuer_company.id
                }
            )
        else:
            # Issuer CIK matches filing CIK, just ensure company info is up to date
            pass

    async def _ensure_ticker_lookup(self, session: AsyncSession, filing: Filing) -> None:
        """Ensure ticker is looked up and updated for all filings."""
        # Skip if ticker is already set
        if filing.ticker:
            return
        
        # Initialize Redis client for caching
        settings = Settings()
        redis_client = Redis.from_url(settings.redis_url)
        ticker_service = TickerLookupService(redis_client=redis_client)
        
        # Look up ticker for the filing's CIK
        ticker = await ticker_service.get_ticker_for_cik(filing.cik)
        
        if ticker:
            # Update filing ticker
            filing.ticker = ticker
            
            # Update company ticker if it's missing
            if filing.company and not filing.company.ticker:
                filing.company.ticker = ticker
                
            LOGGER.info(
                "Updated filing ticker from CIK lookup",
                extra={
                    "accession": filing.accession_number,
                    "cik": filing.cik,
                    "ticker": ticker,
                    "form_type": filing.form_type
                }
            )
        else:
            LOGGER.debug(
                "No ticker found for CIK",
                extra={
                    "accession": filing.accession_number,
                    "cik": filing.cik,
                    "form_type": filing.form_type
                }
            )

    async def _try_process_form4_issuer_from_raw(self, task: ParseTask) -> None:
        """Try to process Form 4, Form 144, Schedule 13D/A, and Form 3 issuer 
        information from raw content even if parsing failed."""
        async with self._session_factory() as session:
            stmt = select(Filing).where(Filing.accession_number == task.accession_number)
            filing = (await session.execute(stmt)).scalar_one_or_none()
            if filing is None or filing.form_type not in ['4', '144', 'SCHEDULE 13D/A', '3']:
                return
            
            # Extract issuer CIK from raw filing content (XML)
            issuer_cik = None
            issuer_name = None
            
            # Try the raw blob content
            blob_stmt = (
                select(FilingBlob)
                .where(FilingBlob.filing_id == filing.id, FilingBlob.kind == 'raw')
            )
            raw_blob = (await session.execute(blob_stmt)).scalar_one_or_none()
            
            if raw_blob:
                try:
                    raw_content = await self._fetcher.fetch(raw_blob.location)
                    raw_text = raw_content.decode('utf-8', errors='ignore')
                    issuer_cik = extract_issuer_cik(raw_text)
                    issuer_name = extract_issuer_name(raw_text)
                    if issuer_cik:
                        LOGGER.info(
                            "Extracted issuer CIK from raw content for failed parsing",
                            extra={
                                "accession": filing.accession_number,
                                "issuer_cik": issuer_cik,
                                "issuer_name": issuer_name,
                                "original_cik": filing.cik
                            }
                        )
                except Exception as e:
                    LOGGER.warning(
                        "Failed to fetch raw blob content for failed parsing",
                        extra={"accession": filing.accession_number, "error": str(e)}
                    )
            
            if not issuer_cik:
                LOGGER.warning(
                    "Could not extract issuer CIK from failed Form 4/144/"
                    "Schedule 13D/A/Form 3 filing",
                    extra={"accession": filing.accession_number}
                )
                return
            
            # If issuer CIK is different from filing CIK, update the company association
            if issuer_cik != filing.cik:
                # Check if issuer company already exists
                issuer_company_stmt = select(Company).where(Company.cik == issuer_cik)
                issuer_company = (await session.execute(issuer_company_stmt)).scalar_one_or_none()
                
                if issuer_company is None:
                    # Create new company for the issuer
                    # Initialize Redis client for caching
                    settings = Settings()
                    redis_client = Redis.from_url(settings.redis_url)
                    ticker_service = TickerLookupService(redis_client=redis_client)
                    company_info = await ticker_service.get_company_info_for_cik(issuer_cik)
                    
                    issuer_company = Company(
                        cik=issuer_cik,
                        name=(
                            issuer_name or
                            company_info.get("company_name", f"Company {issuer_cik}")
                            if company_info else 
                            (issuer_name or f"Company {issuer_cik}")
                        ),
                        ticker=company_info.get("ticker") if company_info else None
                    )
                    session.add(issuer_company)
                    await session.flush()
                    
                    LOGGER.info(
                        "Created new issuer company for failed parsing",
                        extra={
                            "accession": filing.accession_number,
                            "issuer_cik": issuer_cik,
                            "company_name": issuer_company.name,
                            "ticker": issuer_company.ticker
                        }
                    )
                else:
                    # Update existing issuer company info if needed
                    # Initialize Redis client for caching
                    settings = Settings()
                    redis_client = Redis.from_url(settings.redis_url)
                    ticker_service = TickerLookupService(redis_client=redis_client)
                    company_info = await ticker_service.get_company_info_for_cik(issuer_cik)
                    
                    if company_info:
                        company_name = company_info.get("company_name")
                        ticker = company_info.get("ticker")
                        if (company_name and
                            issuer_company.name.startswith("Company ")):
                            issuer_company.name = company_name
                        if ticker and not issuer_company.ticker:
                            issuer_company.ticker = ticker
                    
                    LOGGER.info(
                        "Updated existing issuer company for failed parsing",
                        extra={
                            "accession": filing.accession_number,
                            "issuer_cik": issuer_cik,
                            "company_name": issuer_company.name,
                            "ticker": issuer_company.ticker
                        }
                    )
                
                # Update filing to point to the correct issuer company
                filing.company_id = issuer_company.id
                filing.cik = issuer_cik
                filing.ticker = issuer_company.ticker
                
                await session.commit()
                
                LOGGER.info(
                    "Updated filing company association for failed parsing",
                    extra={
                        "accession": filing.accession_number,
                        "old_cik": filing.cik,
                        "new_cik": issuer_cik,
                        "company_id": issuer_company.id
                    }
                )
            else:
                # Issuer CIK matches filing CIK, just ensure company info is up to date
                # Initialize Redis client for caching
                settings = Settings()
                redis_client = Redis.from_url(settings.redis_url)
                ticker_service = TickerLookupService(redis_client=redis_client)
                company_info = await ticker_service.get_company_info_for_cik(issuer_cik)
                
                if company_info and filing.company:
                    company_name = company_info.get("company_name")
                    ticker = company_info.get("ticker")
                    if (company_name and
                        filing.company.name.startswith("Company ")):
                        filing.company.name = company_name
                    if ticker and not filing.company.ticker:
                        filing.company.ticker = ticker
                        filing.ticker = ticker

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

    async def _schedule_diff_jobs(
        self,
        *,
        filing_id: int | None,
        company_id: int | None,
        form_type: str | None,
        filed_at: datetime | None,
        accession_number: str,
    ) -> None:
        if self._diff_queue is None:
            return
        if (
            filing_id is None
            or company_id is None
            or form_type is None
            or filed_at is None
        ):
            return

        tasks: list[DiffTask] = []

        async with self._session_factory() as session:
            async with session.begin():
                current_filing = (
                    await session.execute(
                        select(Filing)
                        .where(Filing.id == filing_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if current_filing is None:
                    return

                previous_filing = (
                    await session.execute(
                        select(Filing)
                        .where(
                            Filing.company_id == company_id,
                            Filing.form_type == form_type,
                            Filing.filed_at < filed_at,
                        )
                        .order_by(Filing.filed_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if previous_filing is None:
                    return

                current_sections = (
                    await session.execute(
                        select(FilingSection)
                        .where(FilingSection.filing_id == current_filing.id)
                        .order_by(FilingSection.ordinal)
                    )
                ).scalars().all()
                previous_sections = (
                    await session.execute(
                        select(FilingSection)
                        .where(FilingSection.filing_id == previous_filing.id)
                        .order_by(FilingSection.ordinal)
                    )
                ).scalars().all()

                if not current_sections and not previous_sections:
                    return

                diff_record = (
                    await session.execute(
                        select(FilingDiff)
                        .where(FilingDiff.current_filing_id == current_filing.id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()

                if diff_record is None:
                    diff_record = FilingDiff(
                        current_filing_id=current_filing.id,
                        previous_filing_id=previous_filing.id,
                        status=DiffStatus.PENDING.value,
                        expected_sections=0,
                        processed_sections=0,
                    )
                    session.add(diff_record)
                    await session.flush()
                else:
                    diff_record.previous_filing_id = previous_filing.id
                    diff_record.status = DiffStatus.PENDING.value
                    diff_record.expected_sections = 0
                    diff_record.processed_sections = 0
                    diff_record.last_error = None
                    await session.execute(
                        delete(FilingSectionDiff).where(
                            FilingSectionDiff.filing_diff_id == diff_record.id
                        )
                    )

                current_map = {section.ordinal: section for section in current_sections}
                previous_map = {section.ordinal: section for section in previous_sections}
                ordinals = sorted(set(current_map.keys()) | set(previous_map.keys()))

                for ordinal in ordinals:
                    current_section = current_map.get(ordinal)
                    previous_section = previous_map.get(ordinal)
                    if current_section is None and previous_section is None:
                        continue
                    change_kind = (
                        "update"
                        if current_section is not None and previous_section is not None
                        else "addition"
                        if current_section is not None
                        else "removal"
                    )
                    if current_section is not None:
                        title = current_section.title
                    elif previous_section is not None:
                        title = previous_section.title
                    else:
                        title = f"Section {ordinal}"
                    job_id = f"{accession_number}:diff:{ordinal}:{change_kind}"
                    tasks.append(
                        DiffTask(
                            job_id=job_id,
                            diff_id=diff_record.id,
                            current_filing_id=current_filing.id,
                            previous_filing_id=previous_filing.id,
                            current_section_id=current_section.id
                            if current_section is not None
                            else None,
                            previous_section_id=previous_section.id
                            if previous_section is not None
                            else None,
                            section_ordinal=ordinal,
                            section_title=title,
                        )
                    )

                diff_record.expected_sections = len(tasks)
                if diff_record.expected_sections == 0:
                    diff_record.status = DiffStatus.SKIPPED.value

        if not tasks or self._diff_queue is None:
            return
        for task in tasks:
            if self._diff_backpressure is not None:
                await self._diff_backpressure.wait_if_needed()
            await self._diff_queue.push(task)


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
