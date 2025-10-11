"""Prometheus metrics for Groq section summarization jobs."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

SECTION_SUMMARY_LATENCY_SECONDS = Histogram(
    "sec_section_summary_latency_seconds",
    "Latency for Groq section chunk summarization jobs",
    ["model"],
)

SECTION_SUMMARY_COMPLETIONS_TOTAL = Counter(
    "sec_section_summary_completions_total",
    "Completed section summarization jobs",
    ["model"],
)

SECTION_SUMMARY_ERRORS_TOTAL = Counter(
    "sec_section_summary_errors_total",
    "Section summarization errors grouped by stage",
    ["stage"],
)

SECTION_SUMMARY_TOKENS_TOTAL = Counter(
    "sec_section_summary_tokens_total",
    "Tokens consumed by section summarization jobs",
    ["kind"],
)
