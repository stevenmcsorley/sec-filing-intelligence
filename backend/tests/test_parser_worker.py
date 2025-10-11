from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.db import Base
from app.downloader.storage import LocalFilesystemStorageBackend
from app.ingestion.models import ParseTask
from app.models.company import Company
from app.models.filing import BlobKind, Filing, FilingBlob, FilingSection, FilingStatus
from app.parsing.queue import InMemoryParseQueue
from app.parsing.worker import ParserOptions, ParserWorker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


async def _setup_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_parser_worker_creates_sections(tmp_path: Path) -> None:
    session_factory = await _setup_session_factory()
    raw_path = tmp_path / "0001234567" / "0001234567-25-000001" / "submission.txt"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    sample_text = (
        Path(__file__).parent / "fixtures" / "parsing" / "sample_text.txt"
    ).read_text()
    raw_path.write_text(sample_text)

    async with session_factory() as session:
        async with session.begin():
            company = Company(cik="0001234567", name="Example Co")
            session.add(company)
            await session.flush()
            filing = Filing(
                company_id=company.id,
                cik="0001234567",
                form_type="10-K",
                filed_at=datetime.now(UTC),
                accession_number="0001234567-25-000001",
                source_urls=json.dumps(["https://example.com"]),
                status=FilingStatus.DOWNLOADED.value,
            )
            session.add(filing)
            await session.flush()
            blob = FilingBlob(
                filing_id=filing.id,
                kind=BlobKind.RAW.value,
                location=f"file://{raw_path}",
                content_type="text/plain",
            )
            session.add(blob)

    storage = LocalFilesystemStorageBackend(tmp_path)
    queue = InMemoryParseQueue()
    options = ParserOptions(max_retries=1, backoff_seconds=0)
    worker = ParserWorker(
        name="parser-test",
        queue=queue,
        session_factory=session_factory,
        fetcher=storage,
        options=options,
    )

    await worker._handle_task(ParseTask(accession_number="0001234567-25-000001"))  # type: ignore[attr-defined]

    async with session_factory() as session:
        stmt = select(Filing).where(Filing.accession_number == "0001234567-25-000001")
        filing = (await session.execute(stmt)).scalar_one()
        assert filing.status == FilingStatus.PARSED.value
        sections = (
            await session.execute(select(FilingSection).where(FilingSection.filing_id == filing.id))
        ).scalars().all()
        assert len(sections) == 3


@pytest.mark.asyncio
async def test_parser_worker_run_handles_exceptions(tmp_path: Path) -> None:
    session_factory = await _setup_session_factory()

    triggered = asyncio.Event()

    class FailingParserWorker(ParserWorker):
        async def _handle_task(self, task: ParseTask) -> None:  # type: ignore[override]
            triggered.set()
            raise RuntimeError("boom")

    queue = InMemoryParseQueue()
    storage = LocalFilesystemStorageBackend(tmp_path)
    worker = FailingParserWorker(
        name="parser-failing",
        queue=queue,
        session_factory=session_factory,
        fetcher=storage,
        options=ParserOptions(max_retries=0, backoff_seconds=0),
    )

    await queue.push(ParseTask(accession_number="0000000000-00-000000"))
    stop_event = asyncio.Event()
    run_task = asyncio.create_task(worker.run(stop_event))
    await asyncio.wait_for(triggered.wait(), timeout=1)
    stop_event.set()
    await asyncio.wait_for(run_task, timeout=1)
    assert run_task.exception() is None
