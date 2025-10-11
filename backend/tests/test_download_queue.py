from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from app.downloader.queue import InMemoryDownloadQueue
from app.ingestion.models import DownloadTask


def _task(accession: str) -> DownloadTask:
    return DownloadTask(
        accession_number=accession,
        cik="0000000001",
        form_type="8-K",
        filing_href="https://example.com/filing",
        filed_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_in_memory_queue_deduplicates() -> None:
    queue = InMemoryDownloadQueue()
    task = _task("0001")

    inserted = await queue.push(task)
    assert inserted is True

    duplicate = await queue.push(task)
    assert duplicate is False

    message = await queue.pop(timeout=1)
    assert message is not None
    await queue.ack(message)

    # After ack the task can be enqueued again
    inserted_again = await queue.push(task)
    assert inserted_again is True

    await queue.close()


@pytest.mark.asyncio
async def test_in_memory_queue_visibility_requeue() -> None:
    queue = InMemoryDownloadQueue(visibility_timeout=0.1)
    task = _task("0002")
    await queue.push(task)

    first = await queue.pop(timeout=1)
    assert first is not None

    # Allow the visibility timeout to expire without acking
    await asyncio.sleep(0.2)

    second = await queue.pop(timeout=1)
    assert second is not None
    assert second.task.accession_number == task.accession_number

    await queue.ack(second)
    await queue.close()


@pytest.mark.asyncio
async def test_in_memory_queue_stale_ack_noop() -> None:
    queue = InMemoryDownloadQueue(visibility_timeout=0.05)
    task = _task("0003")
    await queue.push(task)

    first = await queue.pop(timeout=1)
    assert first is not None

    await asyncio.sleep(0.1)
    second = await queue.pop(timeout=1)
    assert second is not None
    assert second.task.accession_number == task.accession_number

    # Stale ack should be ignored, leaving dedupe entry intact
    await queue.ack(first)
    assert await queue.push(task) is False

    await queue.ack(second)
    # Now dedupe released
    assert await queue.push(task) is True
    await queue.close()
