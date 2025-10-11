from __future__ import annotations

from collections import deque

import pytest
from app.ingestion.backpressure import QueueBackpressure
from app.ingestion.metrics import BACKPRESSURE_EVENTS_COUNTER


class _DummyRedis:
    def __init__(self, depths: list[int]) -> None:
        self._depths = deque(depths)

    async def llen(self, _: str) -> int:
        if self._depths:
            return self._depths.popleft()
        return 0


@pytest.mark.asyncio
async def test_backpressure_pause_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _DummyRedis([600, 600, 300])
    controller = QueueBackpressure(
        redis,
        "sec:ingestion:download",
        pause_threshold=500,
        resume_threshold=350,
        check_interval=0.01,
    )

    sleep_calls: list[float] = []

    async def _sleep(interval: float) -> None:
        sleep_calls.append(interval)

    monkeypatch.setattr("app.ingestion.backpressure.asyncio.sleep", _sleep)

    pause_initial = BACKPRESSURE_EVENTS_COUNTER.labels(
        "sec:ingestion:download", "pause"
    )._value.get()  # type: ignore[attr-defined]
    resume_initial = BACKPRESSURE_EVENTS_COUNTER.labels(
        "sec:ingestion:download", "resume"
    )._value.get()  # type: ignore[attr-defined]

    await controller.wait_if_needed()

    pause_final = BACKPRESSURE_EVENTS_COUNTER.labels(
        "sec:ingestion:download", "pause"
    )._value.get()  # type: ignore[attr-defined]
    resume_final = BACKPRESSURE_EVENTS_COUNTER.labels(
        "sec:ingestion:download", "resume"
    )._value.get()  # type: ignore[attr-defined]

    assert pause_final == pause_initial + 1
    assert resume_final == resume_initial + 1
    # Controller should have slept while backpressure active
    assert sleep_calls
