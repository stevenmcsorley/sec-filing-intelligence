"""Service wiring for download workers."""

from __future__ import annotations

import asyncio
import logging

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db import get_session_factory

from .queue import DownloadQueue, RedisDownloadQueue
from .storage import MinioStorageBackend, StorageBackend
from .worker import DownloadOptions, DownloadWorker

LOGGER = logging.getLogger(__name__)


class DownloadService:
    """Manage downloader worker lifecycle."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._queue: DownloadQueue | None = None
        self._storage: StorageBackend | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._stop_event = asyncio.Event()
        self._started = False

    async def start(self) -> None:
        if not self._settings.downloader_enabled:
            LOGGER.info("Downloader disabled via configuration")
            return

        if self._started:
            return

        redis = Redis.from_url(
            self._settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self._queue = RedisDownloadQueue(redis, self._settings.edgar_download_queue_name)

        self._storage = MinioStorageBackend(
            endpoint=self._settings.minio_endpoint,
            access_key=self._settings.minio_access_key,
            secret_key=self._settings.minio_secret_key,
            bucket=self._settings.minio_filings_bucket,
            secure=self._settings.minio_secure,
            region=self._settings.minio_region,
        )

        self._http_client = httpx.AsyncClient(
            headers={"User-Agent": self._settings.edgar_user_agent},
            follow_redirects=True,
        )

        self._session_factory = get_session_factory()
        options = DownloadOptions(
            max_retries=self._settings.downloader_max_retries,
            backoff_seconds=self._settings.downloader_backoff_seconds,
            request_timeout=self._settings.downloader_request_timeout,
        )

        for index in range(self._settings.downloader_concurrency):
            worker = DownloadWorker(
                name=f"downloader-{index}",
                queue=self._queue,
                session_factory=self._session_factory,
                storage=self._storage,
                http_client=self._http_client,
                options=options,
            )
            task = asyncio.create_task(worker.run(self._stop_event))
            self._tasks.append(task)

        self._started = True
        LOGGER.info("Downloader service started", extra={"workers": len(self._tasks)})

    async def stop(self) -> None:
        if not self._started:
            return

        self._stop_event.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

        if self._queue is not None:
            await self._queue.close()
            self._queue = None

        self._tasks.clear()
        self._started = False
        LOGGER.info("Downloader service stopped")
