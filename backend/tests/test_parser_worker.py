from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.db import Base
from app.diff.queue import InMemoryDiffQueue
from app.downloader.storage import LocalFilesystemStorageBackend
from app.ingestion.models import ParseTask
from app.models.company import Company
from app.models.diff import FilingDiff
from app.models.filing import BlobKind, Filing, FilingBlob, FilingSection, FilingStatus
from app.orchestration.planner import ChunkPlanner, ChunkPlannerOptions
from app.orchestration.queue import InMemoryChunkQueue
from app.parsing.queue import InMemoryParseQueue
from app.parsing.worker import ChunkQueueTarget, ParserOptions, ParserWorker
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
    chunk_queue = InMemoryChunkQueue()
    chunk_planner = ChunkPlanner(
        ChunkPlannerOptions(max_tokens_per_chunk=400, min_tokens_per_chunk=10)
    )
    worker = ParserWorker(
        name="parser-test",
        queue=queue,
        session_factory=session_factory,
        fetcher=storage,
        options=options,
        chunk_targets=[ChunkQueueTarget(queue=chunk_queue)],
        chunk_planner=chunk_planner,
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

    message = await chunk_queue.pop(timeout=1)
    assert message is not None
    assert message.task.accession_number == "0001234567-25-000001"
    assert message.task.content
    await chunk_queue.ack(message)


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


@pytest.mark.asyncio
async def test_parser_worker_schedules_diff_jobs(tmp_path: Path) -> None:
    session_factory = await _setup_session_factory()
    raw_path = tmp_path / "0001234568" / "0001234568-25-000001" / "submission.txt"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    sample_text = (
        Path(__file__).parent / "fixtures" / "parsing" / "sample_text.txt"
    ).read_text()
    raw_path.write_text(sample_text)

    async with session_factory() as session:
        async with session.begin():
            company = Company(cik="0001234568", name="Diff Example Co")
            session.add(company)
            await session.flush()
            previous_filing = Filing(
                company_id=company.id,
                cik="0001234568",
                form_type="10-K",
                filed_at=datetime.now(UTC) - timedelta(days=365),
                accession_number="0001234568-24-000001",
                source_urls=json.dumps(["https://example.com/prev"]),
                status=FilingStatus.PARSED.value,
            )
            session.add(previous_filing)
            await session.flush()
            # Seed prior sections
            session.add_all(
                [
                    FilingSection(
                        filing_id=previous_filing.id,
                        title="Item 1. Business",
                        ordinal=1,
                        content="Legacy business description.",
                    ),
                    FilingSection(
                        filing_id=previous_filing.id,
                        title="Item 1A. Risk Factors",
                        ordinal=2,
                        content="Legacy risks listed here.",
                    ),
                    FilingSection(
                        filing_id=previous_filing.id,
                        title="Item 2. Properties",
                        ordinal=3,
                        content="Legacy property details.",
                    ),
                ]
            )
            current_filing = Filing(
                company_id=company.id,
                cik="0001234568",
                form_type="10-K",
                filed_at=datetime.now(UTC),
                accession_number="0001234568-25-000001",
                source_urls=json.dumps(["https://example.com"]),
                status=FilingStatus.DOWNLOADED.value,
            )
            session.add(current_filing)
            await session.flush()
            blob = FilingBlob(
                filing_id=current_filing.id,
                kind=BlobKind.RAW.value,
                location=f"file://{raw_path}",
                content_type="text/plain",
            )
            session.add(blob)

    storage = LocalFilesystemStorageBackend(tmp_path)
    queue = InMemoryParseQueue()
    options = ParserOptions(max_retries=1, backoff_seconds=0)
    chunk_queue = InMemoryChunkQueue()
    diff_queue = InMemoryDiffQueue()
    chunk_planner = ChunkPlanner(
        ChunkPlannerOptions(max_tokens_per_chunk=400, min_tokens_per_chunk=10)
    )
    worker = ParserWorker(
        name="parser-diff",
        queue=queue,
        session_factory=session_factory,
        fetcher=storage,
        options=options,
        chunk_targets=[ChunkQueueTarget(queue=chunk_queue)],
        chunk_planner=chunk_planner,
        diff_queue=diff_queue,
    )

    await worker._handle_task(ParseTask(accession_number="0001234568-25-000001"))  # type: ignore[attr-defined]

    ordinals: list[int] = []
    for _ in range(3):
        message = await diff_queue.pop(timeout=1)
        assert message is not None
        ordinals.append(message.task.section_ordinal)
    assert sorted(ordinals) == [1, 2, 3]

    async with session_factory() as session:
        diff_record = (
            await session.execute(
                select(FilingDiff).where(FilingDiff.current_filing.has(accession_number="0001234568-25-000001"))
            )
        ).scalar_one()
        assert diff_record.expected_sections == 3
