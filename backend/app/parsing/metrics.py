"""Prometheus metrics for parsing pipeline."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

PARSER_LATENCY_SECONDS = Histogram(
    "sec_parser_latency_seconds",
    "Latency of parsing filings",
)

PARSER_SECTIONS_TOTAL = Counter(
    "sec_parser_sections_total",
    "Number of sections produced",
)

PARSER_ERRORS_TOTAL = Counter(
    "sec_parser_errors_total",
    "Parsing errors grouped by stage",
    ["stage"],
)
