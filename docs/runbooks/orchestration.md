# Groq Orchestration Runbook

## Overview

Once filings are parsed, the chunk planner segments each section into LLM-friendly jobs and enqueues them on the Groq processing queue (`sec:groq:chunk`). Each chunk task carries:

- Filing accession number and section metadata
- Chunk index plus paragraph offsets (start/end)
- Normalized text content
- Estimated token count (heuristic based on word count × 1.3)

Workers downstream can consume these jobs reliably thanks to dedupe keys and visibility timeouts.

## Configuration

Environment variables (see `config/backend.env.example`):

| Variable | Description | Default |
| --- | --- | --- |
| `CHUNK_QUEUE_NAME` | Redis list used for Groq chunk jobs. | `sec:groq:chunk` |
| `CHUNK_QUEUE_VISIBILITY_TIMEOUT_SECONDS` | Seconds before an unacked job is requeued. | `600` |
| `CHUNK_QUEUE_REQUEUE_BATCH_SIZE` | Max expired jobs reclaimed per sweep. | `200` |
| `CHUNK_QUEUE_PAUSE_THRESHOLD` | Queue depth that pauses new chunk generation. | `1000` |
| `CHUNK_QUEUE_RESUME_THRESHOLD` | Queue depth that resumes planning after pause. | `750` |
| `CHUNK_BACKPRESSURE_CHECK_INTERVAL_SECONDS` | Poll interval while backpressure is active. | `1.0` |
| `CHUNKER_MAX_TOKENS_PER_CHUNK` | Upper bound on estimated tokens per chunk. | `800` |
| `CHUNKER_MIN_TOKENS_PER_CHUNK` | Minimum tokens before planner greedily adds more paragraphs. | `200` |
| `CHUNKER_PARAGRAPH_OVERLAP` | Paragraph overlap between successive chunks. | `1` |

## Metrics

- `sec_chunk_planner_latency_seconds` — Histogram tracking planning latency.
- `sec_chunk_planner_chunks_total{form_type}` — Counter of chunk jobs emitted per filing form type.
- `sec_ingestion_queue_depth{queue_name="sec:groq:chunk"}` — Queue depth gauge (shared with backpressure helper).
- `sec_ingestion_backpressure_events_total{queue_name="sec:groq:chunk",event}` — Pause/resume transitions triggered by backlog.

## Operational Notes

- The planner runs inside parser workers; backpressure guard (`QueueBackpressure`) stops chunk generation when backlog exceeds thresholds.
- Jobs are deduped by `job_id` (`<accession>:<section ordinal>:<chunk index>:<token>`). Stale acknowledgements are ignored to prevent task loss.
- To requeue a specific job manually:
  ```bash
  redis-cli srem ${CHUNK_QUEUE_NAME}:dedupe "<JOB_ID>"
  redis-cli rpush ${CHUNK_QUEUE_NAME} '{"job_id":"<JOB_ID>", ... }'
  ```
- Tests covering chunk planner (`backend/tests/test_chunk_planner.py`) and queue semantics (`backend/tests/test_chunk_queue.py`) should be updated whenever heuristics or payload shape changes.

## Section Summaries Worker

- `SectionSummaryService` consumes chunk jobs and calls Groq chat completions to produce bullet summaries per section chunk.
- Successful completions are persisted in `filing_analyses` with `analysis_type = section_chunk_summary`; tokens consumed feed the `sec_section_summary_tokens_total` counter.
- Retryable provider errors (429/5xx/timeouts) leave the message unacked so Redis requeues after the visibility timeout; fatal 4xx errors are acknowledged and logged.
- Metrics of interest:
  - `sec_section_summary_latency_seconds{model}`
  - `sec_section_summary_errors_total{stage}`
  - `sec_section_summary_completions_total{model}`
