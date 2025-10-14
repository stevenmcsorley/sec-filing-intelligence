"""Application service that orchestrates EDGAR pollers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from redis.asyncio import Redis

from app.downloader.queue import RedisDownloadQueue

from ..config import Settings
from .backpressure import QueueBackpressure
from .feed import EdgarFeedClient
from .metrics import POLL_ERRORS_COUNTER
from .poller import CompanyPollerFactory, Poller
from .queue import RedisQueuePublisher
from .state import RedisAccessionStateStore

LOGGER = logging.getLogger(__name__)


class IngestionService:
    """Manage lifecycle of EDGAR pollers and related infrastructure."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._redis: Redis | None = None
        self._feed_client = EdgarFeedClient(
            base_headers={
                "User-Agent": self._settings.edgar_user_agent,
                "Accept-Encoding": "gzip, deflate",
            }
        )
        self._pollers: list[Poller] = []
        self._tasks: list[asyncio.Task[None]] = []
        self._client_lifespan_cm = self._feed_client.lifespan()
        self._client_lifespan_active = False

    async def start(self) -> None:
        """Start pollers if ingestion is enabled."""
        if not self._settings.edgar_polling_enabled:
            LOGGER.info("EDGAR polling disabled via configuration")
            return

        if not self._settings.redis_url:
            LOGGER.warning("Redis URL missing; disabling ingestion service")
            return

        redis_client = Redis.from_url(
            self._settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self._redis = redis_client
        state_store = RedisAccessionStateStore(
            redis_client,
            key=self._settings.edgar_seen_accessions_key,
        )
        download_queue = RedisDownloadQueue(
            redis_client,
            self._settings.edgar_download_queue_name,
            visibility_timeout=self._settings.downloader_visibility_timeout_seconds,
            requeue_batch_size=self._settings.downloader_requeue_batch_size,
        )
        queue_publisher = RedisQueuePublisher(download_queue)

        # Open HTTP client lifespan
        await self._client_lifespan_cm.__aenter__()
        self._client_lifespan_active = True

        backpressure: QueueBackpressure | None = None
        if self._settings.edgar_download_queue_pause_threshold > 0:
            resume_threshold = max(
                0,
                self._settings.edgar_download_queue_resume_threshold
                or self._settings.edgar_download_queue_pause_threshold // 2,
            )
            backpressure = QueueBackpressure(
                redis_client,
                self._settings.edgar_download_queue_name,
                pause_threshold=self._settings.edgar_download_queue_pause_threshold,
                resume_threshold=resume_threshold,
                check_interval=self._settings.edgar_backpressure_check_interval_seconds,
            )

        # Global poller
        global_feed_url = str(self._settings.edgar_global_feed_url)
        global_poller = Poller(
            name="global",
            interval_seconds=self._settings.edgar_global_poll_interval_seconds,
            fetch_fn=lambda: self._feed_client.fetch_feed(global_feed_url),
            state_store=state_store,
            queue_publisher=queue_publisher,
            backpressure=backpressure,
        )
        self._register_poller(global_poller)

        # Company pollers
        company_ciks = _normalized_ciks(self._settings.edgar_company_ciks)
        if company_ciks:
            factory = CompanyPollerFactory(
                feed_client=self._feed_client,
                base_url=str(self._settings.edgar_company_feed_base_url),
                state_store=state_store,
                queue_publisher=queue_publisher,
                backpressure=backpressure,
                interval_seconds=self._settings.edgar_company_poll_interval_seconds,
            )
            for cik in company_ciks:
                self._register_poller(factory.build(cik))

    async def stop(self) -> None:
        """Stop pollers and close resources."""
        for poller in self._pollers:
            await poller.stop()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        if self._client_lifespan_active:
            await self._client_lifespan_cm.__aexit__(None, None, None)
            self._client_lifespan_active = False

        if self._redis is not None:
            await self._redis.close()
            self._redis = None

        self._pollers.clear()
        self._tasks.clear()

    def _register_poller(self, poller: Poller) -> None:
        task = asyncio.create_task(self._safe_run(poller))
        self._pollers.append(poller)
        self._tasks.append(task)

    async def _safe_run(self, poller: Poller) -> None:
        try:
            await poller.run()
        except asyncio.CancelledError:  # pragma: no cover - control flow
            raise
        except Exception:  # pragma: no cover - logged for observability
            LOGGER.exception("Poller crashed", extra={"feed": poller.name})
            POLL_ERRORS_COUNTER.labels("fatal").inc()


def _normalized_ciks(ciks: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for raw in ciks:
        token = raw.strip()
        if not token:
            continue
        digits = token.lstrip("0") or "0"
        normalized.append(digits.zfill(10))
    return normalized
