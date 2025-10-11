from __future__ import annotations

import asyncio

import pytest
from app.orchestration.planner import ChunkTask
from app.orchestration.queue import InMemoryChunkQueue


def _chunk(job_id: str) -> ChunkTask:
    return ChunkTask(
        job_id=job_id,
        accession_number="0000000000-00-000001",
        section_ordinal=1,
        section_title="Item 1",
        chunk_index=0,
        start_paragraph_index=0,
        end_paragraph_index=1,
        content="Sample content for testing.",
        estimated_tokens=50,
    )


@pytest.mark.asyncio
async def test_chunk_queue_deduplicates_jobs() -> None:
    queue = InMemoryChunkQueue()
    task = _chunk("job-1")
    inserted = await queue.push(task)
    assert inserted is True

    duplicate = await queue.push(task)
    assert duplicate is False

    message = await queue.pop(timeout=1)
    assert message is not None
    await queue.ack(message)

    assert await queue.push(task) is True
    await queue.close()


@pytest.mark.asyncio
async def test_chunk_queue_stale_ack_noop() -> None:
    queue = InMemoryChunkQueue(visibility_timeout=0.05)
    task = _chunk("job-2")
    await queue.push(task)

    first = await queue.pop(timeout=1)
    assert first is not None

    await asyncio.sleep(0.1)
    second = await queue.pop(timeout=1)
    assert second is not None

    await queue.ack(first)  # stale ack ignored
    assert await queue.push(task) is False  # still deduped

    await queue.ack(second)
    assert await queue.push(task) is True
    await queue.close()


@pytest.mark.asyncio
async def test_chunk_queue_requeue_only_once() -> None:
    queue = InMemoryChunkQueue(visibility_timeout=0.01)
    task = _chunk("job-3")
    await queue.push(task)
    message = await queue.pop(timeout=1)
    assert message is not None

    await asyncio.sleep(0.02)
    await queue._requeue_expired()
    await queue._requeue_expired()

    second = await queue.pop(timeout=1)
    assert second is not None
    assert await queue.pop(timeout=0.05) is None
    await queue.ack(second)
    await queue.close()
