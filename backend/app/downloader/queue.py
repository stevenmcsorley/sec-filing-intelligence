"""Queue consumer utilities for download workers."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable
from typing import Protocol, cast

from redis.asyncio import Redis

from app.ingestion.models import DownloadTask


class DownloadQueue(Protocol):
    """Protocol to pop download tasks."""

    async def push(self, task: DownloadTask) -> None:
        """Push a download task onto the queue."""

    async def pop(self, timeout: int = 5) -> DownloadTask | None:
        """Pop a task, waiting up to `timeout` seconds."""

    async def close(self) -> None:
        """Close the queue and release resources."""


class RedisDownloadQueue(DownloadQueue):
    """Queue implementation backed by Redis BLPOP."""

    def __init__(self, redis: Redis, queue_name: str) -> None:
        self._redis = redis
        self._queue_name = queue_name

    async def push(self, task: DownloadTask) -> None:
        payload = json.dumps(task.to_payload())
        result = self._redis.rpush(self._queue_name, payload)
        if isinstance(result, Awaitable):
            await result

    async def pop(self, timeout: int = 5) -> DownloadTask | None:
        raw = self._redis.blpop([self._queue_name], timeout=timeout)
        if isinstance(raw, Awaitable):
            result = await cast(Awaitable[list[str] | None], raw)
        else:
            result = cast(list[str] | None, raw)
        if result is None:
            return None
        _, payload = result
        data = json.loads(payload)
        return DownloadTask.from_payload(data)

    async def close(self) -> None:
        await self._redis.close()


class InMemoryDownloadQueue(DownloadQueue):
    """Async in-memory queue for tests."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[DownloadTask] = asyncio.Queue()

    async def push(self, task: DownloadTask) -> None:
        await self._queue.put(task)

    async def pop(self, timeout: int = 5) -> DownloadTask | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    async def close(self) -> None:
        while not self._queue.empty():
            self._queue.get_nowait()
