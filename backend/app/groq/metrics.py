"""Prometheus metrics related to Groq token budgeting."""

from __future__ import annotations

from prometheus_client import Counter, Gauge

GROQ_BUDGET_USAGE_TOKENS = Gauge(
    "sec_groq_budget_usage_tokens",
    "Total Groq tokens consumed within the current budgeting window",
    ["service", "model"],
)

GROQ_BUDGET_REMAINING_TOKENS = Gauge(
    "sec_groq_budget_remaining_tokens",
    "Remaining Groq token budget within the current window",
    ["service", "model"],
)

GROQ_BUDGET_EXHAUSTIONS_TOTAL = Counter(
    "sec_groq_budget_exhaustions_total",
    "Number of times Groq token budgets were exhausted",
    ["service", "model"],
)

GROQ_BUDGET_DEFERRED_JOBS_TOTAL = Counter(
    "sec_groq_budget_deferred_jobs_total",
    "Jobs deferred due to Groq token budget exhaustion",
    ["service", "model"],
)
