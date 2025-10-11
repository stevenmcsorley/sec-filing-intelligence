"""Queue publisher abstractions for ingestion events."""

from __future__ import annotations

from typing import Protocol

from app.downloader.queue import DownloadQueue

from .models import DownloadTask


class IngestionQueuePublisher(Protocol):
    """Protocol for publishing ingestion tasks."""

    async def publish_download(self, task: DownloadTask) -> None:
        """Publish a download task for downstream workers."""


class RedisQueuePublisher:
    """Publish download tasks using a shared download queue implementation."""

    def __init__(self, queue: DownloadQueue) -> None:
        self._queue = queue

    async def publish_download(self, task: DownloadTask) -> None:
        await self._queue.push(task)


class InMemoryQueuePublisher:
    """In-memory queue used for tests."""

    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def publish_download(self, task: DownloadTask) -> None:
        self.messages.append(task.to_payload())
