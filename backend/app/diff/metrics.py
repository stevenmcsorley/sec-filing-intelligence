"""Prometheus metrics for diff comparison engine."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

DIFF_LATENCY_SECONDS = Histogram(
    "sec_diff_latency_seconds",
    "Latency for section diff jobs",
    ["model"],
)

DIFF_COMPLETIONS_TOTAL = Counter(
    "sec_diff_completions_total",
    "Completed section diff jobs",
    ["model"],
)

DIFF_ERRORS_TOTAL = Counter(
    "sec_diff_errors_total",
    "Section diff errors grouped by stage",
    ["stage"],
)

DIFF_TOKENS_TOTAL = Counter(
    "sec_diff_tokens_total",
    "Tokens consumed by diff jobs",
    ["kind"],
)

DIFF_CHANGES_TOTAL = Counter(
    "sec_diff_changes_total",
    "Number of material changes emitted by diff jobs",
    ["change_type"],
)
