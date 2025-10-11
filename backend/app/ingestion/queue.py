"""Queue publisher abstractions for ingestion events."""

from __future__ import annotations

import json
from collections.abc import Awaitable
from typing import Protocol

from redis.asyncio import Redis

from .models import DownloadTask


class IngestionQueuePublisher(Protocol):
    """Protocol for publishing ingestion tasks."""

    async def publish_download(self, task: DownloadTask) -> None:
        """Publish a download task for downstream workers."""


class RedisQueuePublisher:
    """Publish download tasks via Redis lists (acts as a simple queue)."""

    def __init__(self, redis: Redis, queue_name: str = "sec:ingestion:download") -> None:
        self._redis = redis
        self._queue_name = queue_name

    async def publish_download(self, task: DownloadTask) -> None:
        payload = json.dumps(task.to_payload())
        result = self._redis.rpush(self._queue_name, payload)
        if isinstance(result, Awaitable):
            await result


class InMemoryQueuePublisher:
    """In-memory queue used for tests."""

    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    async def publish_download(self, task: DownloadTask) -> None:
        self.messages.append(task.to_payload())
