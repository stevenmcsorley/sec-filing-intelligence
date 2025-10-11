from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from app.db import Base
from app.diff.queue import DiffQueueMessage, DiffTask, InMemoryDiffQueue
from app.diff.worker import DiffOptions, DiffWorker
from app.models import Company, Filing, FilingAnalysis, FilingSection, FilingStatus
from app.models.diff import DiffStatus, FilingDiff, FilingSectionDiff
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


def _message(task: DiffTask) -> DiffQueueMessage:
    payload = json.dumps(task.to_payload(), sort_keys=True)
    return DiffQueueMessage(task=task, payload=payload, job_id=task.job_id, token="token")


@pytest.mark.asyncio
async def test_diff_worker_persists_changes() -> None:
    session_factory = await _session_factory()

    current_accession = "0001000000-25-000001"
    previous_accession = "0001000000-24-000050"

    async with session_factory() as session:
        async with session.begin():
            company = Company(cik="0001000000", name="Example Corp")
            session.add(company)
            await session.flush()
            previous_filing = Filing(
                company_id=company.id,
                cik=company.cik,
                form_type="10-K",
                filed_at=datetime.now(UTC) - timedelta(days=365),
                accession_number=previous_accession,
                source_urls='["https://example.com/prev"]',
                status=FilingStatus.PARSED.value,
            )
            session.add(previous_filing)
            await session.flush()
            current_filing = Filing(
                company_id=company.id,
                cik=company.cik,
                form_type="10-K",
                filed_at=datetime.now(UTC),
                accession_number=current_accession,
                source_urls='["https://example.com/current"]',
                status=FilingStatus.PARSED.value,
            )
            session.add(current_filing)
            await session.flush()
            session.add(
                FilingSection(
                    filing_id=previous_filing.id,
                    title="Risk Factors",
                    ordinal=1,
                    content="We face currency risk.",
                )
            )
            session.add(
                FilingSection(
                    filing_id=current_filing.id,
                    title="Risk Factors",
                    ordinal=1,
                    content="We face currency risk and supply chain disruptions.",
                )
            )
            session.add(
                FilingDiff(
                    current_filing_id=current_filing.id,
                    previous_filing_id=previous_filing.id,
                    status=DiffStatus.PENDING.value,
                    expected_sections=1,
                    processed_sections=0,
                )
            )

    queue = InMemoryDiffQueue()
    client = _StubClient(
        result=ChatCompletionResult(
            content=json.dumps(
                [
                    {
                        "change_type": "update",
                        "summary": "Expanded risk discussion to include supply chain disruptions.",
                        "impact": "high",
                        "confidence": 0.85,
                        "evidence": "supply chain disruptions",
                    }
                ]
            ),
            model="llama-3.3-70b-versatile",
            prompt_tokens=150,
            completion_tokens=60,
            total_tokens=210,
        )
    )
    worker = DiffWorker(
        name="diff-test",
        queue=queue,
        session_factory=session_factory,
        client=client,
        options=DiffOptions(
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            max_output_tokens=512,
            max_retries=0,
            backoff_seconds=0.1,
        ),
    )

    async with session_factory() as session:
        async with session.begin():
            diff_record = (
                await session.execute(
                    select(FilingDiff).where(FilingDiff.status == DiffStatus.PENDING.value)
                )
            ).scalar_one()
            current_section = (
                await session.execute(
                    select(FilingSection)
                    .where(FilingSection.filing_id == diff_record.current_filing_id)
                    .order_by(FilingSection.ordinal)
                )
            ).scalars().first()
            previous_section = (
                await session.execute(
                    select(FilingSection)
                    .where(FilingSection.filing_id == diff_record.previous_filing_id)
                    .order_by(FilingSection.ordinal)
                )
            ).scalars().first()

    task = DiffTask(
        job_id=f"{current_accession}:diff:1:update",
        diff_id=diff_record.id,
        current_filing_id=diff_record.current_filing_id,
        previous_filing_id=diff_record.previous_filing_id,
        current_section_id=current_section.id if current_section is not None else None,
        previous_section_id=previous_section.id if previous_section is not None else None,
        section_ordinal=1,
        section_title="Risk Factors",
    )
    ack = await worker._handle_message(_message(task))
    assert ack is True

    async with session_factory() as session:
        diff = (
            await session.execute(
                select(FilingDiff).where(FilingDiff.id == diff_record.id)
            )
        ).scalar_one()
        assert diff.status == DiffStatus.COMPLETED.value
        sections = (
            await session.execute(
                select(FilingSectionDiff).where(FilingSectionDiff.filing_diff_id == diff.id)
            )
        ).scalars().all()
        assert len(sections) == 1
        section_diff = sections[0]
        assert section_diff.change_type == "update"
        assert section_diff.impact == "high"
        assert section_diff.analysis_id is not None

        analysis = (
            await session.execute(
                select(FilingAnalysis).where(FilingAnalysis.id == section_diff.analysis_id)
            )
        ).scalar_one()
        assert analysis.analysis_type == "section_diff"


@pytest.mark.asyncio
async def test_diff_worker_no_change_marks_complete() -> None:
    session_factory = await _session_factory()

    async with session_factory() as session:
        async with session.begin():
            company = Company(cik="0002000000", name="Static Inc")
            session.add(company)
            await session.flush()
            previous = Filing(
                company_id=company.id,
                cik=company.cik,
                form_type="10-Q",
                filed_at=datetime.now(UTC) - timedelta(days=90),
                accession_number="0002000000-24-000010",
                source_urls='["https://example.com/prev"]',
                status=FilingStatus.PARSED.value,
            )
            session.add(previous)
            await session.flush()
            current = Filing(
                company_id=company.id,
                cik=company.cik,
                form_type="10-Q",
                filed_at=datetime.now(UTC),
                accession_number="0002000000-25-000010",
                source_urls='["https://example.com/current"]',
                status=FilingStatus.PARSED.value,
            )
            session.add(current)
            await session.flush()
            section_prev = FilingSection(
                filing_id=previous.id,
                title="MD&A",
                ordinal=1,
                content="Discussion remains unchanged.",
            )
            section_curr = FilingSection(
                filing_id=current.id,
                title="MD&A",
                ordinal=1,
                content="Discussion remains unchanged.",
            )
            session.add_all([section_prev, section_curr])
            session.add(
                FilingDiff(
                    current_filing_id=current.id,
                    previous_filing_id=previous.id,
                    status=DiffStatus.PENDING.value,
                    expected_sections=1,
                    processed_sections=0,
                )
            )

    queue = InMemoryDiffQueue()
    client = _StubClient()
    worker = DiffWorker(
        name="diff-test-nochange",
        queue=queue,
        session_factory=session_factory,
        client=client,
        options=DiffOptions(
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            max_output_tokens=512,
            max_retries=0,
            backoff_seconds=0.1,
        ),
    )

    async with session_factory() as session:
        async with session.begin():
            diff_record = (
                await session.execute(select(FilingDiff))
            ).scalar_one()
            current_section = (
                await session.execute(
                    select(FilingSection).where(
                        FilingSection.filing_id == diff_record.current_filing_id
                    )
                )
            ).scalar_one()
            previous_section = (
                await session.execute(
                    select(FilingSection).where(
                        FilingSection.filing_id == diff_record.previous_filing_id
                    )
                )
            ).scalar_one()

    task = DiffTask(
        job_id="0002000000-25-000010:diff:1:update",
        diff_id=diff_record.id,
        current_filing_id=diff_record.current_filing_id,
        previous_filing_id=diff_record.previous_filing_id,
        current_section_id=current_section.id,
        previous_section_id=previous_section.id,
        section_ordinal=1,
        section_title="MD&A",
    )
    ack = await worker._handle_message(_message(task))
    assert ack is True

    async with session_factory() as session:
        diff = (
            await session.execute(select(FilingDiff).where(FilingDiff.id == diff_record.id))
        ).scalar_one()
        assert diff.status == DiffStatus.COMPLETED.value
        assert diff.processed_sections == diff.expected_sections
        section_diffs = (
            await session.execute(
                select(FilingSectionDiff).where(FilingSectionDiff.filing_diff_id == diff.id)
            )
        ).scalars().all()
        assert section_diffs == []
