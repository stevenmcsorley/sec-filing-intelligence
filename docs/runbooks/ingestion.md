# Ingestion Poller Runbook

## Overview

The ingestion service runs periodic pollers against SEC EDGAR Atom feeds. It detects new filings by accession number and enqueues download tasks onto the Redis-backed ingestion queue (`sec:ingestion:download`). Deduplication happens via a Redis set (`sec:ingestion:seen-accessions`) to ensure idempotent processing.

## Configuration

Environment variables (set in `config/backend.env`):

| Variable | Description | Default |
| --- | --- | --- |
| `EDGAR_POLLING_ENABLED` | Toggle ingestion pollers on/off. | `true` |
| `EDGAR_USER_AGENT` | User-Agent presented to SEC; must include contact details per EDGAR policy. | `Mozilla/5.0 (compatible; sec-filing-intel/0.1; support@sec-intel.local)` |
| `EDGAR_GLOBAL_FEED_URL` | Atom feed for global filings. | `https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&count=100&output=atom` |
| `EDGAR_COMPANY_FEED_BASE_URL` | Base URL for company feeds (CIK appended automatically). | `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=` |
| `EDGAR_GLOBAL_POLL_INTERVAL_SECONDS` | Interval for the global feed poller. | `60` |
| `EDGAR_COMPANY_POLL_INTERVAL_SECONDS` | Interval for company pollers. | `300` |
| `EDGAR_COMPANY_CIKS` | Comma-separated list of CIKs to poll individually. | (empty) |
| `EDGAR_DOWNLOAD_QUEUE_NAME` | Redis list used for download tasks. | `sec:ingestion:download` |
| `EDGAR_SEEN_ACCESSIONS_KEY` | Redis set used for accession deduplication. | `sec:ingestion:seen-accessions` |

Redis connectivity is configured via `REDIS_URL` (defaults to `redis://redis:6379/0`).

## Metrics

Prometheus metrics emitted by the pollers:

- `sec_ingestion_feed_fetch_latency_seconds{feed_kind}` — Histogram of feed fetch latency.
- `sec_ingestion_new_filings_total{feed_kind,form_type}` — Counter of newly discovered filings.
- `sec_ingestion_poll_errors_total{feed_kind}` — Counter of errors while polling feeds. `feed_kind="fatal"` indicates an unexpected crash in the polling loop.

These metrics are registered automatically when the ingestion service starts. They appear on the default Prometheus registry; expose them via the metrics endpoint configured in the observability stack.

## Logging

Pollers log at `INFO` level during start-up and `DEBUG` after each cycle (includes number of new items). Exceptions are logged at `ERROR` with the feed name attached in JSON structured fields (`extra={"feed": ...}`).

## Operational Notes

- Always run with a valid SEC-compliant `User-Agent`. Requests without it will be throttled.
- To pause ingestion temporarily, set `EDGAR_POLLING_ENABLED=false` and restart the backend service.
- The deduplication set can be cleared (e.g., in staging) by deleting the Redis key defined in `EDGAR_SEEN_ACCESSIONS_KEY`.
- Download workers consume JSON payloads produced by the pollers via `RedisQueuePublisher`. Ensure downstream workers understand the schema: `accession_number`, `cik`, `form_type`, `filing_href`.
