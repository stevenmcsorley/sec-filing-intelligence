"""Service wiring for parser workers."""

from __future__ import annotations

import asyncio
import logging

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db import get_session_factory
from app.downloader.storage import MinioStorageBackend
from app.ingestion.backpressure import QueueBackpressure
from app.ingestion.models import ParseTask
from app.orchestration.planner import ChunkPlanner, ChunkPlannerOptions
from app.orchestration.queue import ChunkQueue, RedisChunkQueue

from .queue import ParseQueue, RedisParseQueue
from .worker import ParserOptions, ParserWorker

LOGGER = logging.getLogger(__name__)


class ParserService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._queue: ParseQueue | None = None
        self._storage: MinioStorageBackend | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._chunk_queue: ChunkQueue | None = None
        self._chunk_backpressure: QueueBackpressure | None = None
        self._chunk_planner: ChunkPlanner | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._stop_event = asyncio.Event()
        self._started = False

    async def start(self) -> None:
        if not self._settings.parser_enabled:
            LOGGER.info("Parser disabled via configuration")
            return
        if self._started:
            return

        redis = Redis.from_url(
            self._settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self._queue = RedisParseQueue(redis, self._settings.parser_queue_name)
        chunk_redis = Redis.from_url(
            self._settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self._chunk_queue = RedisChunkQueue(
            chunk_redis,
            self._settings.chunk_queue_name,
            visibility_timeout=self._settings.chunk_queue_visibility_timeout_seconds,
            requeue_batch_size=self._settings.chunk_queue_requeue_batch_size,
        )
        if self._settings.chunk_queue_pause_threshold > 0:
            resume_threshold = max(
                0,
                self._settings.chunk_queue_resume_threshold
                or self._settings.chunk_queue_pause_threshold // 2,
            )
            self._chunk_backpressure = QueueBackpressure(
                chunk_redis,
                self._settings.chunk_queue_name,
                pause_threshold=self._settings.chunk_queue_pause_threshold,
                resume_threshold=resume_threshold,
                check_interval=self._settings.chunk_backpressure_check_interval_seconds,
            )
        self._chunk_planner = ChunkPlanner(
            ChunkPlannerOptions(
                max_tokens_per_chunk=self._settings.chunker_max_tokens_per_chunk,
                min_tokens_per_chunk=self._settings.chunker_min_tokens_per_chunk,
                paragraph_overlap=self._settings.chunker_paragraph_overlap,
            )
        )
        self._storage = MinioStorageBackend(
            endpoint=self._settings.minio_endpoint,
            access_key=self._settings.minio_access_key,
            secret_key=self._settings.minio_secret_key,
            bucket=self._settings.minio_filings_bucket,
            secure=self._settings.minio_secure,
            region=self._settings.minio_region,
        )
        self._session_factory = get_session_factory()
        options = ParserOptions(
            max_retries=self._settings.parser_max_retries,
            backoff_seconds=self._settings.parser_backoff_seconds,
        )

        for index in range(self._settings.parser_concurrency):
            worker = ParserWorker(
                name=f"parser-{index}",
                queue=self._queue,
                session_factory=self._session_factory,
                fetcher=self._storage,
                options=options,
                chunk_queue=self._chunk_queue,
                chunk_planner=self._chunk_planner,
                chunk_backpressure=self._chunk_backpressure,
            )
            task = asyncio.create_task(worker.run(self._stop_event))
            self._tasks.append(task)

        self._started = True
        LOGGER.info("Parser service started", extra={"workers": len(self._tasks)})

    async def stop(self) -> None:
        if not self._started:
            return
        self._stop_event.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        if self._queue is not None:
            await self._queue.close()
            self._queue = None
        if self._chunk_queue is not None:
            await self._chunk_queue.close()
            self._chunk_queue = None
        self._tasks.clear()
        self._started = False
        LOGGER.info("Parser service stopped")

    async def enqueue(self, task: ParseTask) -> None:
        if self._queue is None:
            raise RuntimeError("Parser service not started")
        await self._queue.push(task)
