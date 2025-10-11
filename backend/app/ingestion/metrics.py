"""Prometheus metrics for the ingestion pipeline."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

FETCH_LATENCY_SECONDS = Histogram(
    "sec_ingestion_feed_fetch_latency_seconds",
    "Latency fetching SEC EDGAR feeds",
    ["feed_kind"],
)

NEW_FILINGS_COUNTER = Counter(
    "sec_ingestion_new_filings_total",
    "Number of new filings discovered by pollers",
    ["feed_kind", "form_type"],
)

POLL_ERRORS_COUNTER = Counter(
    "sec_ingestion_poll_errors_total",
    "Number of poller errors encountered",
    ["feed_kind"],
)
