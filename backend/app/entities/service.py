"""Service wiring for entity extraction workers."""

from __future__ import annotations

import asyncio
import logging

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db import get_session_factory
from app.orchestration.queue import RedisChunkQueue
from app.summarization.client import GroqChatClient

from .worker import EntityExtractionOptions, EntityExtractionWorker

LOGGER = logging.getLogger(__name__)


class EntityExtractionService:
    """Manage lifecycle of entity extraction workers."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._queue: RedisChunkQueue | None = None
        self._client: GroqChatClient | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._stop_event = asyncio.Event()
        self._started = False

    async def start(self) -> None:
        if not self._settings.entity_extraction_enabled:
            LOGGER.info("Entity extraction disabled via configuration")
            return
        if self._settings.groq_api_key in (None, ""):
            LOGGER.warning("Groq API key missing; entity extraction disabled")
            return
        if self._settings.entity_concurrency <= 0:
            LOGGER.info("Entity extraction concurrency set to 0; skipping startup")
            return
        if self._started:
            return

        redis = Redis.from_url(
            self._settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self._queue = RedisChunkQueue(
            redis,
            self._settings.entity_queue_name,
            visibility_timeout=self._settings.entity_queue_visibility_timeout_seconds,
            requeue_batch_size=self._settings.entity_queue_requeue_batch_size,
        )
        api_key = self._settings.groq_api_key
        assert api_key is not None  # for mypy; validated above
        self._client = GroqChatClient(
            api_key=api_key,
            base_url=str(self._settings.groq_api_url),
            timeout=self._settings.entity_request_timeout,
        )
        session_factory = get_session_factory()
        self._session_factory = session_factory
        options = EntityExtractionOptions(
            model=self._settings.entity_model,
            temperature=self._settings.entity_temperature,
            max_output_tokens=self._settings.entity_max_output_tokens,
            max_retries=self._settings.entity_max_retries,
            backoff_seconds=self._settings.entity_backoff_seconds,
        )

        for index in range(self._settings.entity_concurrency):
            worker = EntityExtractionWorker(
                name=f"entity-{index}",
                queue=self._queue,
                session_factory=session_factory,
                client=self._client,
                options=options,
            )
            task = asyncio.create_task(worker.run(self._stop_event))
            self._tasks.append(task)

        self._started = True
        LOGGER.info("Entity extraction service started", extra={"workers": len(self._tasks)})

    async def stop(self) -> None:
        if not self._started:
            return

        self._stop_event.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        if self._queue is not None:
            await self._queue.close()
            self._queue = None

        if self._client is not None:
            await self._client.aclose()
            self._client = None

        self._stop_event = asyncio.Event()
        self._started = False
        LOGGER.info("Entity extraction service stopped")
