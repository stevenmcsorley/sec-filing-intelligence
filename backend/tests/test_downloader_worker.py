from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from app.db import Base
from app.downloader.queue import InMemoryDownloadQueue
from app.downloader.storage import LocalFilesystemStorageBackend
from app.downloader.worker import DownloadOptions, DownloadWorker
from app.ingestion.models import DownloadTask
from app.models.company import Company
from app.models.filing import BlobKind, Filing, FilingBlob, FilingStatus
from app.parsing.queue import InMemoryParseQueue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


async def _setup_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_download_worker_persists_artifacts(tmp_path: Path) -> None:
    session_factory = await _setup_session_factory()
    queue = InMemoryDownloadQueue()
    parse_queue = InMemoryParseQueue()
    options = DownloadOptions(max_retries=2, backoff_seconds=0, request_timeout=5)

    filing_href = "https://example.com/Archive/0001234567-25-000001-index.htm"
    task = DownloadTask(
        accession_number="0001234567-25-000001",
        cik="0001234567",
        form_type="10-K",
        filing_href=filing_href,
        filed_at=datetime.now(UTC),
    )

    responses = {
        filing_href.replace("-index.htm", ".txt"): httpx.Response(
            200,
            text="raw document",
            headers={"Content-Type": "text/plain"},
        ),
        filing_href: httpx.Response(
            200,
            text="<html>index</html>",
            headers={"Content-Type": "text/html"},
        ),
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        response = responses.get(str(request.url))
        if response is None:
            return httpx.Response(404)
        return response

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        storage = LocalFilesystemStorageBackend(tmp_path)
        worker = DownloadWorker(
            name="worker-test",
            queue=queue,
            session_factory=session_factory,
            storage=storage,
            http_client=client,
            options=options,
            parse_queue=parse_queue,
        )

        await worker._handle_task(task)  # type: ignore[attr-defined]

    parse_task = await parse_queue.pop(timeout=1)
    assert parse_task is not None
    assert parse_task.accession_number == task.accession_number

    async with session_factory() as session:
        stmt = select(Filing).where(Filing.accession_number == task.accession_number)
        filing = (await session.execute(stmt)).scalar_one()
        assert filing.status == FilingStatus.DOWNLOADED.value
        assert filing.downloaded_at is not None

        blob_stmt = select(FilingBlob).where(FilingBlob.filing_id == filing.id)
        blobs = (await session.execute(blob_stmt)).scalars().all()
        kinds = {blob.kind for blob in blobs}
        assert kinds == {BlobKind.RAW.value, BlobKind.INDEX.value}

        raw_blob = next(blob for blob in blobs if blob.kind == BlobKind.RAW.value)
        raw_path = tmp_path / f"{task.cik}/{task.accession_number}/submission.txt"
        assert raw_blob.location.endswith("submission.txt")
        assert raw_blob.checksum == hashlib.sha256(b"raw document").hexdigest()
        assert raw_path.exists()


@pytest.mark.asyncio
async def test_download_worker_marks_failure(tmp_path: Path) -> None:
    session_factory = await _setup_session_factory()
    options = DownloadOptions(max_retries=0, backoff_seconds=0, request_timeout=1)
    filing_href = "https://example.com/Archive/0002222222-25-000001-index.htm"
    task = DownloadTask(
        accession_number="0002222222-25-000001",
        cik="0002222222",
        form_type="8-K",
        filing_href=filing_href,
        filed_at=datetime.now(UTC),
    )

    async with session_factory() as session:
        async with session.begin():
            company = Company(cik=task.cik, name="Test Company")
            session.add(company)
            await session.flush()
            filing = Filing(
                company_id=company.id,
                cik=task.cik,
                ticker=None,
                form_type=task.form_type,
                filed_at=task.filed_at,
                accession_number=task.accession_number,
                source_urls=json.dumps([task.filing_href]),
                status=FilingStatus.PENDING.value,
            )
            session.add(filing)

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    parse_queue = InMemoryParseQueue()
    async with httpx.AsyncClient(transport=transport) as client:
        storage = LocalFilesystemStorageBackend(tmp_path)
        queue = InMemoryDownloadQueue()
        worker = DownloadWorker(
            name="worker-test",
            queue=queue,
            session_factory=session_factory,
            storage=storage,
            http_client=client,
            options=options,
            parse_queue=parse_queue,
        )

        await worker._handle_task(task)  # type: ignore[attr-defined]

    async with session_factory() as session:
        stmt = select(Filing).where(Filing.accession_number == task.accession_number)
        filing = (await session.execute(stmt)).scalar_one()
        assert filing.status == FilingStatus.FAILED.value
    assert await parse_queue.pop(timeout=1) is None


@pytest.mark.asyncio
async def test_concurrent_company_creation_race_condition() -> None:
    """Test that concurrent company creation doesn't cause IntegrityError."""
    session_factory = await _setup_session_factory()

    # Use a single session for all operations to simulate real concurrent access
    async with session_factory() as session:
        # Create multiple tasks that try to create the same company
        async def create_company_task(cik: str, company_name: str) -> None:
            from datetime import datetime

            from app.downloader.worker import DownloadWorker
            from app.ingestion.models import DownloadTask

            # Create a mock task
            task = DownloadTask(
                accession_number=f"{cik}-25-000001",
                cik=cik,
                form_type="10-K",
                filing_href=f"https://example.com/{cik}-index.htm",
                filed_at=datetime.now(UTC),
                company_name=company_name,
            )

            # Create a mock worker instance just to test the company creation logic
            worker = DownloadWorker(
                name="test-worker",
                queue=None,  # type: ignore
                session_factory=session_factory,
                storage=None,  # type: ignore
                http_client=None,  # type: ignore
                options=None,  # type: ignore
                parse_queue=None,  # type: ignore
            )

            # Call the company creation method directly
            company = await worker._get_or_create_company(session, task)  # type: ignore[attr-defined]
            assert company.cik == cik
            # Company name should be set to one of the provided names (race condition winner)
            assert company.name.startswith("Test Company")

        # Run multiple concurrent tasks trying to create the same company
        tasks = []
        for i in range(10):
            task = create_company_task("1234567890", f"Test Company {i}")
            tasks.append(task)

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

        # Verify only one company was created
        from app.models.company import Company
        from sqlalchemy import select
        stmt = select(Company).where(Company.cik == "1234567890")
        companies = (await session.execute(stmt)).scalars().all()
        assert len(companies) == 1
        company = companies[0]
        # Company name should be one of the test names (race condition winner)
        assert company.name in [f"Test Company {i}" for i in range(10)]
