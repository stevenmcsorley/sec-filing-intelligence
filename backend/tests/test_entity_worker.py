from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.db import Base
from app.entities.worker import EntityExtractionOptions, EntityExtractionWorker
from app.models import Company, Filing, FilingAnalysis, FilingEntity, FilingSection, FilingStatus
from app.models.analysis import AnalysisType
from app.orchestration.planner import ChunkTask
from app.orchestration.queue import ChunkQueueMessage, InMemoryChunkQueue
from app.summarization.client import ChatCompletionResult
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
        job_id=f"{accession}:1:0:entity",
        accession_number=accession,
        section_ordinal=1,
        section_title="Risk Factors",
        chunk_index=0,
        start_paragraph_index=0,
        end_paragraph_index=0,
                    content=(
                        "The Chief Financial Officer, Pat Jones, resigned effective March 1, 2025."
                    ),
        estimated_tokens=120,
    )


def _message(task: ChunkTask) -> ChunkQueueMessage:
    payload = json.dumps(task.to_payload(), sort_keys=True)
    return ChunkQueueMessage(task=task, payload=payload, job_id=task.job_id, token="token")


@pytest.mark.asyncio
async def test_entity_worker_persists_entities(tmp_path: Path) -> None:
    session_factory = await _session_factory()

    async with session_factory() as session:
        async with session.begin():
            company = Company(cik="0005550000", name="Example Holdings")
            session.add(company)
            await session.flush()
            filing = Filing(
                company_id=company.id,
                cik=company.cik,
                form_type="8-K",
                filed_at=datetime.now(UTC),
                accession_number="0005550000-25-000001",
                source_urls=json.dumps(["https://example.com"]),
                status=FilingStatus.PARSED.value,
            )
            session.add(filing)
            await session.flush()
            session.add(
                FilingSection(
                    filing_id=filing.id,
                    title="Risk Factors",
                    ordinal=1,
                    content=(
                        "The Chief Financial Officer, Pat Jones, resigned effective March 1, 2025."
                    ),
                )
            )

    queue = InMemoryChunkQueue()
    client = _StubClient(
        result=ChatCompletionResult(
            content=json.dumps(
                [
                    {
                        "type": "executive_change",
                        "entity": "CFO Pat Jones resigned effective March 1, 2025",
                        "confidence": 0.92,
                        "evidence": (
                            "The Chief Financial Officer, Pat Jones, resigned effective March 1, "
                            "2025."
                        ),
                        "metadata": {
                            "role": "Chief Financial Officer",
                            "effective_date": "2025-03-01",
                        },
                    }
                ]
            ),
            model="llama-3.3-70b-versatile",
            prompt_tokens=120,
            completion_tokens=45,
            total_tokens=165,
        )
    )
    worker = EntityExtractionWorker(
        name="entity-test",
        queue=queue,
        session_factory=session_factory,
        client=client,
        options=EntityExtractionOptions(
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            max_output_tokens=512,
            max_retries=0,
            backoff_seconds=0.1,
        ),
    )

    message = _message(_chunk_task("0005550000-25-000001"))
    ack = await worker._handle_message(message)
    assert ack is True

    async with session_factory() as session:
        stmt = select(FilingAnalysis).where(FilingAnalysis.job_id == message.job_id)
        analysis = (await session.execute(stmt)).scalar_one()
        assert analysis.analysis_type == AnalysisType.ENTITY_EXTRACTION.value
        assert json.loads(analysis.content)  # ensure JSON stored
        stmt = select(FilingEntity).where(FilingEntity.analysis_id == analysis.id)
        entities = (await session.execute(stmt)).scalars().all()
        assert len(entities) == 1
        entity = entities[0]
        assert entity.entity_type == "executive_change"
        assert entity.label.startswith("CFO Pat Jones")
        assert entity.confidence == pytest.approx(0.92)
        assert json.loads(entity.attributes or "{}")["effective_date"] == "2025-03-01"


@pytest.mark.asyncio
async def test_entity_worker_handles_invalid_json(tmp_path: Path) -> None:
    session_factory = await _session_factory()

    async with session_factory() as session:
        async with session.begin():
            company = Company(cik="0001110000", name="No Entities Inc")
            session.add(company)
            await session.flush()
            filing = Filing(
                company_id=company.id,
                cik=company.cik,
                form_type="10-Q",
                filed_at=datetime.now(UTC),
                accession_number="0001110000-25-000100",
                source_urls=json.dumps(["https://example.com"]),
                status=FilingStatus.PARSED.value,
            )
            session.add(filing)
            await session.flush()
            session.add(
                FilingSection(
                    filing_id=filing.id,
                    title="Management Discussion",
                    ordinal=1,
                    content="General discussion with no material updates.",
                )
            )

    queue = InMemoryChunkQueue()
    client = _StubClient(
        result=ChatCompletionResult(
            content="not-json",
            model="llama-3.3-70b-versatile",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
    )
    worker = EntityExtractionWorker(
        name="entity-test",
        queue=queue,
        session_factory=session_factory,
        client=client,
        options=EntityExtractionOptions(
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            max_output_tokens=512,
            max_retries=0,
            backoff_seconds=0.1,
        ),
    )

    message = _message(_chunk_task("0001110000-25-000100"))
    ack = await worker._handle_message(message)
    assert ack is True

    async with session_factory() as session:
        stmt = (
            select(FilingEntity)
            .join(FilingAnalysis)
            .where(FilingAnalysis.job_id == message.job_id)
        )
        assert (await session.execute(stmt)).scalars().first() is None
