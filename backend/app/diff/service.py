"""Service wiring for filing diff workers."""

from __future__ import annotations

import asyncio
import logging

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db import get_session_factory
from app.groq.budget import TokenBudgetManager
from app.summarization.client import GroqChatClient

from .queue import DiffQueue, RedisDiffQueue
from .worker import DiffOptions, DiffWorker

LOGGER = logging.getLogger(__name__)


class DiffService:
    """Manage lifecycle of diff workers."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._queue: DiffQueue | None = None
        self._client: GroqChatClient | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._budget_manager: TokenBudgetManager | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._stop_event = asyncio.Event()
        self._started = False

    async def start(self) -> None:
        if not self._settings.diff_enabled:
            LOGGER.info("Diff service disabled via configuration")
            return
        if self._settings.groq_api_key in (None, ""):
            LOGGER.warning("Groq API key missing; diff service disabled")
            return
        if self._settings.diff_concurrency <= 0:
            LOGGER.info("Diff concurrency set to 0; skipping startup")
            return
        if self._started:
            return

        redis = Redis.from_url(
            self._settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self._queue = RedisDiffQueue(
            redis,
            self._settings.diff_queue_name,
            visibility_timeout=self._settings.diff_queue_visibility_timeout_seconds,
            requeue_batch_size=self._settings.diff_queue_requeue_batch_size,
        )
        self._budget_manager = TokenBudgetManager(
            redis,
            cooldown_seconds=self._settings.groq_budget_cooldown_seconds,
        )
        budget = self._budget_manager.limiter(
            service="diff",
            model=self._settings.diff_model,
            daily_limit=self._settings.diff_daily_token_budget,
        )

        api_key = self._settings.groq_api_key
        assert api_key is not None  # validated above
        self._client = GroqChatClient(
            api_key=api_key,
            base_url=str(self._settings.groq_api_url),
            timeout=self._settings.diff_request_timeout,
        )
        self._session_factory = get_session_factory()
        options = DiffOptions(
            model=self._settings.diff_model,
            temperature=self._settings.diff_temperature,
            max_output_tokens=self._settings.diff_max_output_tokens,
            max_retries=self._settings.diff_max_retries,
            backoff_seconds=self._settings.diff_backoff_seconds,
        )

        for index in range(self._settings.diff_concurrency):
            worker = DiffWorker(
                name=f"diff-{index}",
                queue=self._queue,
                session_factory=self._session_factory,
                client=self._client,
                options=options,
                budget=budget,
            )
            task = asyncio.create_task(worker.run(self._stop_event))
            self._tasks.append(task)

        self._started = True
        LOGGER.info("Diff service started", extra={"workers": len(self._tasks)})

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

        self._budget_manager = None
        self._stop_event = asyncio.Event()
        self._started = False
        LOGGER.info("Diff service stopped")
