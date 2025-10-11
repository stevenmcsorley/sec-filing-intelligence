"""Prometheus metrics for entity extraction jobs."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

ENTITY_EXTRACTION_LATENCY_SECONDS = Histogram(
    "sec_entity_extraction_latency_seconds",
    "Latency for Groq entity extraction jobs",
    ["model"],
)

ENTITY_EXTRACTION_COMPLETIONS_TOTAL = Counter(
    "sec_entity_extraction_completions_total",
    "Completed entity extraction jobs",
    ["model"],
)

ENTITY_EXTRACTION_ERRORS_TOTAL = Counter(
    "sec_entity_extraction_errors_total",
    "Entity extraction errors grouped by stage",
    ["stage"],
)

ENTITY_EXTRACTION_TOKENS_TOTAL = Counter(
    "sec_entity_extraction_tokens_total",
    "Tokens consumed by entity extraction jobs",
    ["kind"],
)

ENTITY_EXTRACTION_ENTITIES_TOTAL = Counter(
    "sec_entity_extraction_entities_total",
    "Count of entities captured per extraction job",
    ["entity_type"],
)
