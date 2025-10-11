"""Download worker that retrieves filings and stores them in MinIO."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import mimetypes
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ingestion.models import DownloadTask, ParseTask
from app.models.company import Company
from app.models.filing import BlobKind, Filing, FilingBlob, FilingStatus
from app.parsing.queue import ParseQueue

from .metrics import DOWNLOAD_BYTES_TOTAL, DOWNLOAD_ERRORS_TOTAL, DOWNLOAD_LATENCY_SECONDS
from .queue import DownloadQueue
from .storage import StorageBackend, StoredArtifact

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DownloadOptions:
    max_retries: int
    backoff_seconds: float
    request_timeout: float


@dataclass(slots=True)
class ArtifactSpec:
    url: str
    filename: str
    kind: BlobKind


class DownloadWorker:
    """Consumes download tasks and persists artifacts."""

    def __init__(
        self,
        *,
        name: str,
        queue: DownloadQueue,
        session_factory: async_sessionmaker[AsyncSession],
        storage: StorageBackend,
        http_client: httpx.AsyncClient,
        options: DownloadOptions,
        parse_queue: ParseQueue,
    ) -> None:
        self._name = name
        self._queue = queue
        self._session_factory = session_factory
        self._storage = storage
        self._http = http_client
        self._options = options
        self._parse_queue = parse_queue

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            task = await self._queue.pop(timeout=5)
            if task is None:
                continue
            try:
                await self._handle_task(task)
            except Exception:  # pragma: no cover - defensive logging
                LOGGER.exception(
                    "Download worker crashed",
                    extra={"accession": task.accession_number},
                )

    async def _handle_task(self, task: DownloadTask) -> None:
        artifacts = self._build_artifacts(task)
        start_time = datetime.now(UTC)
        for spec in artifacts:
            try:
                data, content_type = await self._fetch_with_retry(spec.url)
            except Exception as exc:  # pragma: no cover - logged below
                LOGGER.error(
                    "Failed to download artifact",
                    extra={
                        "worker": self._name,
                        "accession": task.accession_number,
                        "artifact": spec.filename,
                        "error": str(exc),
                    },
                )
                DOWNLOAD_ERRORS_TOTAL.labels("http", spec.kind.value).inc()
                await self._mark_failed(task)
                return

            checksum = hashlib.sha256(data).hexdigest()
            if content_type is None:
                guessed, _ = mimetypes.guess_type(spec.filename)
                content_type = guessed

            try:
                stored = await self._storage.store(self._object_key(task, spec), data, content_type)
            except Exception as exc:  # pragma: no cover - logged below
                LOGGER.error(
                    "Failed to persist artifact",
                    extra={
                        "worker": self._name,
                        "accession": task.accession_number,
                        "artifact": spec.filename,
                        "error": str(exc),
                    },
                )
                DOWNLOAD_ERRORS_TOTAL.labels("storage", spec.kind.value).inc()
                await self._mark_failed(task)
                return

            try:
                await self._persist_metadata(task, spec, stored, checksum)
            except Exception as exc:  # pragma: no cover - logged below
                LOGGER.error(
                    "Failed to persist metadata",
                    extra={
                        "worker": self._name,
                        "accession": task.accession_number,
                        "artifact": spec.filename,
                        "error": str(exc),
                    },
                )
                DOWNLOAD_ERRORS_TOTAL.labels("db", spec.kind.value).inc()
                await self._mark_failed(task)
                return

            DOWNLOAD_BYTES_TOTAL.labels(spec.kind.value).inc(len(data))

        elapsed = (datetime.now(UTC) - start_time).total_seconds()
        for spec in artifacts:
            DOWNLOAD_LATENCY_SECONDS.labels(spec.kind.value).observe(elapsed)
        await self._parse_queue.push(ParseTask(accession_number=task.accession_number))

    async def _mark_failed(self, task: DownloadTask) -> None:
        async with self._session_factory() as session:
            stmt = select(Filing).where(Filing.accession_number == task.accession_number)
            result = await session.execute(stmt)
            filing = result.scalar_one_or_none()
            if filing is None:
                async with session.begin():
                    company = await self._get_or_create_company(session, task)
                    filing = await self._get_or_create_filing(session, company, task)
            filing.status = FilingStatus.FAILED.value
            await session.commit()

    async def _persist_metadata(
        self,
        task: DownloadTask,
        spec: ArtifactSpec,
        stored: StoredArtifact,
        checksum: str,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                company = await self._get_or_create_company(session, task)
                filing = await self._get_or_create_filing(session, company, task)
                await self._upsert_blob(session, filing, spec, stored, checksum)
                filing.status = FilingStatus.DOWNLOADED.value
                filing.downloaded_at = datetime.now(UTC)

    async def _get_or_create_company(
        self, session: AsyncSession, task: DownloadTask
    ) -> Company:
        stmt = select(Company).where(Company.cik == task.cik)
        result = await session.execute(stmt)
        company = result.scalar_one_or_none()
        if company is not None:
            company.ticker = task.ticker
            return company

        company = Company(cik=task.cik, name=f"Company {task.cik}", ticker=task.ticker)
        session.add(company)
        await session.flush()
        return company

    async def _get_or_create_filing(
        self, session: AsyncSession, company: Company, task: DownloadTask
    ) -> Filing:
        stmt = select(Filing).where(Filing.accession_number == task.accession_number)
        result = await session.execute(stmt)
        filing = result.scalar_one_or_none()
        source_urls = json.dumps(self._source_urls(task))

        if filing is None:
            filing = Filing(
                company_id=company.id,
                cik=task.cik,
                ticker=task.ticker,
                form_type=task.form_type,
                filed_at=task.filed_at,
                accession_number=task.accession_number,
                source_urls=source_urls,
                status=FilingStatus.PENDING.value,
            )
            session.add(filing)
            await session.flush()
            return filing

        filing.company_id = company.id
        filing.cik = task.cik
        filing.ticker = task.ticker
        filing.form_type = task.form_type
        filing.filed_at = task.filed_at
        filing.source_urls = source_urls
        return filing

    async def _upsert_blob(
        self,
        session: AsyncSession,
        filing: Filing,
        spec: ArtifactSpec,
        stored: StoredArtifact,
        checksum: str,
    ) -> None:
        stmt = select(FilingBlob).where(
            FilingBlob.filing_id == filing.id,
            FilingBlob.kind == spec.kind.value,
        )
        result = await session.execute(stmt)
        blob = result.scalar_one_or_none()
        if blob is None:
            blob = FilingBlob(
                filing_id=filing.id,
                kind=spec.kind.value,
                location=stored.location,
                checksum=checksum,
                content_type=stored.content_type,
            )
            session.add(blob)
        else:
            blob.location = stored.location
            blob.checksum = checksum
            blob.content_type = stored.content_type

    async def _fetch_with_retry(self, url: str) -> tuple[bytes, str | None]:
        attempt = 0
        delay = self._options.backoff_seconds
        while True:
            try:
                response = await self._http.get(url, timeout=self._options.request_timeout)
                response.raise_for_status()
                return response.content, response.headers.get("Content-Type")
            except Exception:
                attempt += 1
                if attempt > self._options.max_retries:
                    raise
                await asyncio.sleep(delay)
                delay *= 2

    def _build_artifacts(self, task: DownloadTask) -> list[ArtifactSpec]:
        artifacts: list[ArtifactSpec] = []
        txt_url = self._txt_url(task.filing_href)
        if txt_url is not None:
            artifacts.append(
                ArtifactSpec(
                    url=txt_url,
                    filename="submission.txt",
                    kind=BlobKind.RAW,
                )
            )
        artifacts.append(
            ArtifactSpec(
                url=task.filing_href,
                filename="index.html",
                kind=BlobKind.INDEX,
            )
        )
        return artifacts

    def _txt_url(self, filing_href: str) -> str | None:
        if filing_href.endswith("-index.htm"):
            return filing_href.replace("-index.htm", ".txt")
        if filing_href.endswith("-index.html"):
            return filing_href.replace("-index.html", ".txt")
        return None

    def _object_key(self, task: DownloadTask, spec: ArtifactSpec) -> str:
        return f"{task.cik}/{task.accession_number}/{spec.filename}"

    def _source_urls(self, task: DownloadTask) -> list[str]:
        urls = [task.filing_href]
        txt_url = self._txt_url(task.filing_href)
        if txt_url:
            urls.append(txt_url)
        return urls
