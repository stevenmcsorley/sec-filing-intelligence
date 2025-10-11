from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from app.db import Base
from app.models import Company, Filing, FilingAnalysis, FilingSection
from app.models.filing import FilingStatus
from app.orchestration.planner import ChunkTask
from app.orchestration.queue import InMemoryChunkQueue
from app.summarization.client import ChatCompletionResult
from app.summarization.worker import SectionSummaryOptions, SectionSummaryWorker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class _StubClient:
    def __init__(
        self,
        *,
        result: ChatCompletionResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self._result = result
        self._error = error

    async def chat_completion(self, **_: object) -> ChatCompletionResult:
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


async def _session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


def _chunk_task(accession: str) -> ChunkTask:
    return ChunkTask(
        job_id=f"{accession}:1:0",
        accession_number=accession,
        section_ordinal=1,
        section_title="Management Discussion",
        chunk_index=0,
        start_paragraph_index=0,
        end_paragraph_index=2,
        content="Revenue increased year over year with improved guidance.",
        estimated_tokens=320,
    )


def _options(**kwargs: object) -> SectionSummaryOptions:
    return SectionSummaryOptions(
        model="mixtral",
        temperature=0.2,
        max_output_tokens=200,
        max_retries=int(kwargs.get("max_retries", 0)),
        backoff_seconds=float(kwargs.get("backoff_seconds", 0.01)),
    )


@pytest.mark.asyncio
async def test_section_summary_worker_persists_analysis() -> None:
    session_factory = await _session_factory()
    accession = "0001112223-25-000001"

    async with session_factory() as session:
        async with session.begin():
            company = Company(cik="0001112223", name="Summary Corp")
            session.add(company)
            await session.flush()
            filing = Filing(
                company_id=company.id,
                cik=company.cik,
                form_type="10-K",
                filed_at=datetime.now(UTC),
                accession_number=accession,
                source_urls='["https://example.com"]',
                status=FilingStatus.PARSED.value,
            )
            session.add(filing)
            await session.flush()
            section = FilingSection(
                filing_id=filing.id,
                title="Management Discussion",
                ordinal=1,
                content="Revenue increased year over year with improved guidance.",
            )
            session.add(section)

    queue = InMemoryChunkQueue()
    task = _chunk_task(accession)
    await queue.push(task)
    message = await queue.pop(timeout=1)
    assert message is not None

    client = _StubClient(
        result=ChatCompletionResult(
            content="- Revenue up 12% YoY driven by subscription growth.",
            model="mixtral",
            prompt_tokens=360,
            completion_tokens=90,
            total_tokens=450,
        )
    )

    worker = SectionSummaryWorker(
        name="summary-test",
        queue=queue,
        session_factory=session_factory,
        client=client,
        options=_options(),
    )

    ack = await worker._handle_message(message)
    assert ack is True
    await queue.ack(message)

    async with session_factory() as session:
        stmt = select(FilingAnalysis).where(FilingAnalysis.job_id == message.job_id)
        analysis = (await session.execute(stmt)).scalar_one_or_none()
        assert analysis is not None
        assert analysis.content.startswith("- Revenue up")
        assert analysis.prompt_tokens == 360
        assert analysis.chunk_index == 0


@pytest.mark.asyncio
async def test_section_summary_worker_handles_missing_section() -> None:
    session_factory = await _session_factory()
    accession = "0009998887-25-000001"

    queue = InMemoryChunkQueue()
    task = _chunk_task(accession)
    await queue.push(task)
    message = await queue.pop(timeout=1)
    assert message is not None

    client = _StubClient(
        result=ChatCompletionResult(
            content="- Placeholder",
            model="mixtral",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
    )

    worker = SectionSummaryWorker(
        name="summary-missing",
        queue=queue,
        session_factory=session_factory,
        client=client,
        options=_options(),
    )

    ack = await worker._handle_message(message)
    assert ack is True
    await queue.ack(message)

    async with session_factory() as session:
        stmt = select(FilingAnalysis).where(FilingAnalysis.job_id == message.job_id)
        assert (await session.execute(stmt)).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_section_summary_worker_retryable_error() -> None:
    session_factory = await _session_factory()
    accession = "0001234500-25-000001"

    async with session_factory() as session:
        async with session.begin():
            company = Company(cik="0001234500", name="Retry Corp")
            session.add(company)
            await session.flush()
            filing = Filing(
                company_id=company.id,
                cik=company.cik,
                form_type="8-K",
                filed_at=datetime.now(UTC),
                accession_number=accession,
                source_urls='["https://example.com"]',
                status=FilingStatus.PARSED.value,
            )
            session.add(filing)
            await session.flush()
            section = FilingSection(
                filing_id=filing.id,
                title="Risk Factors",
                ordinal=1,
                content="Risk disclosures updated.",
            )
            session.add(section)

    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(status_code=500, request=request)
    error = httpx.HTTPStatusError("server error", request=request, response=response)

    queue = InMemoryChunkQueue()
    task = _chunk_task(accession)
    await queue.push(task)
    message = await queue.pop(timeout=1)
    assert message is not None

    client = _StubClient(error=error)

    worker = SectionSummaryWorker(
        name="summary-retry",
        queue=queue,
        session_factory=session_factory,
        client=client,
        options=_options(max_retries=0, backoff_seconds=0),
    )

    ack = await worker._handle_message(message)
    assert ack is False
    await queue.ack(message)

    async with session_factory() as session:
        stmt = select(FilingAnalysis).where(FilingAnalysis.job_id == message.job_id)
        assert (await session.execute(stmt)).scalar_one_or_none() is None
