"""Prometheus metrics for the filing downloader."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

DOWNLOAD_LATENCY_SECONDS = Histogram(
    "sec_downloader_latency_seconds",
    "Latency for downloading filing artifacts",
    ["artifact"],
)

DOWNLOAD_BYTES_TOTAL = Counter(
    "sec_downloader_bytes_total",
    "Total bytes persisted per artifact",
    ["artifact"],
)

DOWNLOAD_ERRORS_TOTAL = Counter(
    "sec_downloader_errors_total",
    "Download errors grouped by stage",
    ["stage", "artifact"],
)
