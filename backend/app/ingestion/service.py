"""Application service that orchestrates EDGAR pollers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from redis.asyncio import Redis

from ..config import Settings
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
        self._client_lifespan_token: object | None = None

    async def start(self) -> None:
        """Start pollers if ingestion is enabled."""
        if not self._settings.edgar_polling_enabled:
            LOGGER.info("EDGAR polling disabled via configuration")
            return

        if not self._settings.redis_url:
            LOGGER.warning("Redis URL missing; disabling ingestion service")
            return

        self._redis = Redis.from_url(
            self._settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        state_store = RedisAccessionStateStore(
            self._redis,
            key=self._settings.edgar_seen_accessions_key,
        )
        queue_publisher = RedisQueuePublisher(
            self._redis, queue_name=self._settings.edgar_download_queue_name
        )

        # Open HTTP client lifespan
        self._client_lifespan_token = await self._client_lifespan_cm.__aenter__()

        # Global poller
        global_poller = Poller(
            name="global",
            interval_seconds=self._settings.edgar_global_poll_interval_seconds,
            fetch_fn=lambda: self._feed_client.fetch_feed(self._settings.edgar_global_feed_url),
            state_store=state_store,
            queue_publisher=queue_publisher,
        )
        self._register_poller(global_poller)

        # Company pollers
        company_ciks = _normalized_ciks(self._settings.edgar_company_ciks)
        if company_ciks:
            factory = CompanyPollerFactory(
                feed_client=self._feed_client,
                base_url=self._settings.edgar_company_feed_base_url,
                state_store=state_store,
                queue_publisher=queue_publisher,
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

        if self._client_lifespan_token is not None:
            await self._client_lifespan_cm.__aexit__(None, None, None)
            self._client_lifespan_token = None

        if self._redis is not None:
            await self._redis.aclose()
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
