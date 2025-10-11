from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.ingestion.metrics import POLL_ERRORS_COUNTER
from app.ingestion.models import FilingFeedEntry
from app.ingestion.poller import Poller
from app.ingestion.queue import InMemoryQueuePublisher
from app.ingestion.state import InMemoryAccessionStateStore


def _entry(accession: str, cik: str, form_type: str) -> FilingFeedEntry:
    return FilingFeedEntry(
        accession_number=accession,
        cik=cik,
        form_type=form_type,
        filing_href=f"https://example.com/{accession}",
        filed_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_poller_deduplicates_and_enqueues() -> None:
    cycles: deque[list[FilingFeedEntry]] = deque(
        [
            [_entry("0001", "0000000001", "10-K"), _entry("0002", "0000000002", "8-K")],
            [_entry("0001", "0000000001", "10-K"), _entry("0002", "0000000002", "8-K")],
            [_entry("0003", "0000000003", "6-K")],
        ]
    )

    async def fetch() -> list[FilingFeedEntry]:
        if cycles:
            return cycles.popleft()
        return []

    state = InMemoryAccessionStateStore()
    queue = InMemoryQueuePublisher()
    poller = Poller(
        name="test",
        interval_seconds=1,
        fetch_fn=fetch,
        state_store=state,
        queue_publisher=queue,
    )

    await poller._run_once()
    assert len(queue.messages) == 2

    await poller._run_once()
    assert len(queue.messages) == 2  # duplicates ignored

    await poller._run_once()
    assert len(queue.messages) == 3
    accession_numbers = {message["accession_number"] for message in queue.messages}
    assert accession_numbers == {"0001", "0002", "0003"}
    for message in queue.messages:
        assert "filed_at" in message
        datetime.fromisoformat(message["filed_at"])


@pytest.mark.asyncio
async def test_poller_records_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fetch_failure() -> list[FilingFeedEntry]:
        raise RuntimeError("network unavailable")

    state = InMemoryAccessionStateStore()
    queue = InMemoryQueuePublisher()
    poller = Poller(
        name="failure-test",
        interval_seconds=1,
        fetch_fn=fetch_failure,
        state_store=state,
        queue_publisher=queue,
    )

    initial = POLL_ERRORS_COUNTER.labels("failure-test")._value.get()  # type: ignore[attr-defined]
    monkeypatch.setattr("app.ingestion.poller.asyncio.sleep", AsyncMock())

    await poller._run_once()

    final = POLL_ERRORS_COUNTER.labels("failure-test")._value.get()  # type: ignore[attr-defined]
    assert final == initial + 1
    assert queue.messages == []
