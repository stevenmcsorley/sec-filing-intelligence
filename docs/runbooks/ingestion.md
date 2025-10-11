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
| `EDGAR_DOWNLOAD_QUEUE_PAUSE_THRESHOLD` | Queue depth threshold that pauses pollers. (`0` disables.) | `500` |
| `EDGAR_DOWNLOAD_QUEUE_RESUME_THRESHOLD` | Queue depth that resumes pollers once backlog drops. | `350` |
| `EDGAR_BACKPRESSURE_CHECK_INTERVAL_SECONDS` | Sleep interval while backpressure is active. | `1.0` |

Redis connectivity is configured via `REDIS_URL` (defaults to `redis://redis:6379/0`).

### Downloader Configuration

| Variable | Description | Default |
| --- | --- | --- |
| `DOWNLOADER_ENABLED` | Toggle download workers on/off. | `true` |
| `DOWNLOADER_CONCURRENCY` | Number of concurrent worker tasks. | `2` |
| `DOWNLOADER_MAX_RETRIES` | Retry attempts per artifact before marking failed. | `3` |
| `DOWNLOADER_BACKOFF_SECONDS` | Initial exponential backoff in seconds. | `1.5` |
| `DOWNLOADER_REQUEST_TIMEOUT` | HTTP request timeout in seconds. | `30` |
| `DOWNLOADER_VISIBILITY_TIMEOUT_SECONDS` | Visibility timeout before tasks are requeued. | `60` |
| `DOWNLOADER_REQUEUE_BATCH_SIZE` | Maximum expired tasks reclaimed per sweep. | `100` |
| `MINIO_ENDPOINT` | MinIO endpoint (include scheme). | `http://minio:9000` |
| `MINIO_ACCESS_KEY` | MinIO access key. | `filings` |
| `MINIO_SECRET_KEY` | MinIO secret key. | `filingsfilings` |
| `MINIO_SECURE` | Use HTTPS when connecting to MinIO. | `false` |
| `MINIO_REGION` | Optional region definition for MinIO/S3. | (empty) |
| `MINIO_FILINGS_BUCKET` | Bucket where raw filings are stored. | `filings-raw` |

## Metrics

Prometheus metrics emitted by the pollers:

- `sec_ingestion_feed_fetch_latency_seconds{feed_kind}` — Histogram of feed fetch latency.
- `sec_ingestion_new_filings_total{feed_kind,form_type}` — Counter of newly discovered filings.
- `sec_ingestion_poll_errors_total{feed_kind}` — Counter of errors while polling feeds. `feed_kind="fatal"` indicates an unexpected crash in the polling loop.
- `sec_ingestion_queue_depth{queue_name}` — Gauge of current backlog depth for ingestion queues.
- `sec_ingestion_backpressure_events_total{queue_name,event}` — Counter for `pause`/`resume` transitions triggered by backpressure.

These metrics are registered automatically when the ingestion service starts. They appear on the default Prometheus registry; expose them via the metrics endpoint configured in the observability stack.

Downloader workers export complementary metrics:

- `sec_downloader_latency_seconds{artifact}` — Histogram covering end-to-end latency per artifact type (`raw`, `index`).
- `sec_downloader_bytes_total{artifact}` — Counts bytes uploaded to MinIO.
- `sec_downloader_errors_total{stage,artifact}` — Error counter partitioned by stage (`http`, `storage`, `db`).

## Logging

Pollers log at `INFO` level during start-up and `DEBUG` after each cycle (includes number of new items). Exceptions are logged at `ERROR` with the feed name attached in JSON structured fields (`extra={"feed": ...}`).

Downloader workers log each failure with accession number and artifact metadata. Fatal retries mark the filing status as `failed` to surface in dashboards.

## Operational Notes

- Always run with a valid SEC-compliant `User-Agent`. Requests without it will be throttled.
- To pause ingestion temporarily, set `EDGAR_POLLING_ENABLED=false` and restart the backend service.
- The deduplication set can be cleared (e.g., in staging) by deleting the Redis key defined in `EDGAR_SEEN_ACCESSIONS_KEY`.
- Download workers consume JSON payloads produced by the pollers via `RedisDownloadQueue`. Payload schema includes `accession_number`, `cik`, `form_type`, `filing_href`, and `filed_at` (ISO-8601). The queue maintains Redis keys for dedupe (`<queue>:dedupe`) and in-flight tracking (`<queue>:processing*`); avoid manipulating them manually unless reprocessing.
- MinIO bucket policies and lifecycle configuration are stored under `ops/minio/`. Apply them after creating the `filings-raw` bucket: `mc admin bucket remote add` etc.
- For downstream Groq processing queue configuration, see `docs/runbooks/orchestration.md`.

### Reprocessing a Filing

1. Delete existing blobs and reset status:
   ```sql
   DELETE FROM filing_blobs WHERE filing_id = (SELECT id FROM filings WHERE accession_number = '<ACCESSION>');
   UPDATE filings SET status = 'pending', downloaded_at = NULL WHERE accession_number = '<ACCESSION>';
   ```
2. Requeue the download task via Redis CLI (clear the queue dedupe entry first or the task will be ignored):
   ```bash
   redis-cli srem sec:ingestion:download:dedupe "<ACCESSION>"
   redis-cli rpush sec:ingestion:download '{"accession_number":"<ACCESSION>","cik":"<CIK>","form_type":"<FORM>","filing_href":"<URL>","filed_at":"<ISO8601>"}'
   ```
3. Monitor the downloader metrics (`sec_downloader_latency_seconds`, `sec_downloader_errors_total`) to confirm successful processing.
