"""Background polling tasks for EDGAR feeds."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime

from .feed import EdgarFeedClient
from .metrics import FETCH_LATENCY_SECONDS, NEW_FILINGS_COUNTER, POLL_ERRORS_COUNTER
from .models import DownloadTask, FilingFeedEntry
from .queue import IngestionQueuePublisher
from .state import AccessionStateStore

LOGGER = logging.getLogger(__name__)


class Poller:
    """Generic polling loop that fetches feed items and publishes new filings."""

    def __init__(
        self,
        name: str,
        interval_seconds: int,
        fetch_fn: Callable[[], Coroutine[None, None, list[FilingFeedEntry]]],
        state_store: AccessionStateStore,
        queue_publisher: IngestionQueuePublisher,
    ) -> None:
        self._name = name
        self._interval = interval_seconds
        self._fetch_fn = fetch_fn
        self._state_store = state_store
        self._queue_publisher = queue_publisher
        self._stop_event = asyncio.Event()

    @property
    def name(self) -> str:
        return self._name

    async def run(self) -> None:
        """Run the polling loop until stopped."""
        LOGGER.info("Starting poller", extra={"feed": self._name, "interval": self._interval})
        while not self._stop_event.is_set():
            await self._run_once()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval)
            except TimeoutError:
                continue

    async def stop(self) -> None:
        self._stop_event.set()

    async def _run_once(self) -> None:
        start = datetime.now(UTC)
        try:
            entries = await self._fetch_fn()
            elapsed = (datetime.now(UTC) - start).total_seconds()
            FETCH_LATENCY_SECONDS.labels(self._name).observe(elapsed)
        except Exception:  # pragma: no cover - defensive, logged for observability
            LOGGER.exception("Failed to fetch feed", extra={"feed": self._name})
            POLL_ERRORS_COUNTER.labels(self._name).inc()
            # throttle before next retry
            await asyncio.sleep(min(self._interval, 5))
            return

        new_items = 0
        for entry in entries:
            if not entry.accession_number:
                continue

            is_new = await self._state_store.mark_seen(entry.accession_number)
            if not is_new:
                continue

            new_items += 1
            NEW_FILINGS_COUNTER.labels(self._name, entry.form_type or "UNKNOWN").inc()
            await self._queue_publisher.publish_download(
                DownloadTask(
                    accession_number=entry.accession_number,
                    cik=entry.cik,
                    form_type=entry.form_type,
                    filing_href=entry.filing_href,
                    filed_at=entry.filed_at,
                    summary=(entry.extra or {}).get("summary") if entry.extra else None,
                )
            )

        LOGGER.debug(
            "Poll cycle completed",
            extra={"feed": self._name, "new_items": new_items, "total_entries": len(entries)},
        )


class CompanyPollerFactory:
    """Creates poller instances for company-specific feeds."""

    def __init__(
        self,
        feed_client: EdgarFeedClient,
        base_url: str,
        state_store: AccessionStateStore,
        queue_publisher: IngestionQueuePublisher,
        interval_seconds: int,
    ) -> None:
        self._feed_client = feed_client
        self._base_url = base_url
        self._state_store = state_store
        self._queue_publisher = queue_publisher
        self._interval = interval_seconds

    def build(self, cik: str) -> Poller:
        async def fetch() -> list[FilingFeedEntry]:
            url = f"{self._base_url}{cik}&type=&dateb=&owner=exclude&start=0&count=40&output=atom"
            entries = await self._feed_client.fetch_feed(url, company=True)
            # company-level feed is richer, but fetch_feed already normalizes entries
            return entries

        return Poller(
            name=f"company:{cik}",
            interval_seconds=self._interval,
            fetch_fn=fetch,
            state_store=self._state_store,
            queue_publisher=self._queue_publisher,
        )
