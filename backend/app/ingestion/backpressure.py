"""Helpers for coordinating ingestion backpressure based on queue depth."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any, cast

from redis.asyncio import Redis

from .metrics import BACKPRESSURE_EVENTS_COUNTER, QUEUE_DEPTH_GAUGE

LOGGER = logging.getLogger(__name__)


class QueueBackpressure:
    """Simple controller that pauses pollers when the queue backlog is high."""

    def __init__(
        self,
        redis: Redis,
        queue_name: str,
        *,
        pause_threshold: int,
        resume_threshold: int,
        check_interval: float = 1.0,
    ) -> None:
        self._redis = redis
        self._queue_name = queue_name
        self._pause_threshold = max(0, pause_threshold)
        self._resume_threshold = max(0, resume_threshold)
        self._check_interval = max(0.1, check_interval)
        self._paused = False

    async def wait_if_needed(self) -> None:
        """Block while queue depth exceeds configured thresholds."""
        if self._pause_threshold <= 0:
            return

        pause_threshold = self._pause_threshold
        resume_threshold = min(self._resume_threshold, pause_threshold)

        while True:
            depth = await self._pending_depth()
            QUEUE_DEPTH_GAUGE.labels(self._queue_name).set(depth)

            if self._paused:
                if depth <= resume_threshold:
                    self._paused = False
                    BACKPRESSURE_EVENTS_COUNTER.labels(self._queue_name, "resume").inc()
                    LOGGER.info(
                        "Queue backpressure cleared",
                        extra={"queue": self._queue_name, "depth": depth},
                    )
                    return
            else:
                if depth >= pause_threshold:
                    self._paused = True
                    BACKPRESSURE_EVENTS_COUNTER.labels(self._queue_name, "pause").inc()
                    LOGGER.warning(
                        "Queue depth exceeded threshold; pausing pollers",
                        extra={"queue": self._queue_name, "depth": depth},
                    )
                else:
                    return

            await asyncio.sleep(self._check_interval)

    async def _pending_depth(self) -> int:
        return int(
            await cast(
                Coroutine[Any, Any, int],
                self._redis.llen(self._queue_name),
            )
        )
