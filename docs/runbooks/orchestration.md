# Groq Orchestration Runbook

## Overview

Once filings are parsed, the chunk planner segments each section into LLM-friendly jobs and enqueues them on the Groq processing queue (`sec:groq:chunk`). Each chunk task carries:

- Filing accession number and section metadata
- Chunk index plus paragraph offsets (start/end)
- Normalized text content
- Estimated token count (heuristic based on word count × 1.3)

Workers downstream can consume these jobs reliably thanks to dedupe keys and visibility timeouts.

## Configuration

Environment variables (see `config/backend.env.example`; overrides can be placed in `config/backend.env` which docker compose loads after the example file):

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
| `ENTITY_QUEUE_NAME` | Redis list used for entity extraction jobs. | `sec:groq:entity` |
| `ENTITY_QUEUE_VISIBILITY_TIMEOUT_SECONDS` | Seconds before an unacked entity job is requeued. | `600` |
| `ENTITY_QUEUE_PAUSE_THRESHOLD` | Queue depth that pauses new entity jobs. | `1000` |
| `ENTITY_QUEUE_RESUME_THRESHOLD` | Queue depth that resumes entity planning after pause. | `750` |
| `ENTITY_MODEL` | Default Groq model for entity extraction. | `llama-3.3-70b-versatile` |
| `ENTITY_MAX_OUTPUT_TOKENS` | Output token cap for entity responses. | `512` |
| `SUMMARIZER_MODEL` | Groq model for section summaries. | `mixtral-8x7b-32768` |
| `SUMMARIZER_MAX_OUTPUT_TOKENS` | Output token cap for summaries. | `256` |
| `GROQ_BUDGET_COOLDOWN_SECONDS` | Back-off interval before retrying when budgets are exhausted. | `60` |
| `SUMMARIZER_DAILY_TOKEN_BUDGET` | Optional daily token allotment for section summaries; unset disables enforcement. | _unset_ |
| `ENTITY_DAILY_TOKEN_BUDGET` | Optional daily token allotment for entity extraction jobs. | _unset_ |
| `DIFF_DAILY_TOKEN_BUDGET` | Optional daily token allotment for filing diff jobs. | _unset_ |

## Metrics

- `sec_chunk_planner_latency_seconds` — Histogram tracking planning latency.
- `sec_chunk_planner_chunks_total{form_type}` — Counter of chunk jobs emitted per filing form type.
- `sec_ingestion_queue_depth{queue_name="sec:groq:chunk"}` — Queue depth gauge (shared with backpressure helper).
- `sec_ingestion_backpressure_events_total{queue_name="sec:groq:chunk",event}` — Pause/resume transitions triggered by backlog.
- `sec_entity_extraction_latency_seconds{model}` — Latency histogram for entity jobs.
- `sec_entity_extraction_entities_total{entity_type}` — Count of extracted entities per category.
- `sec_groq_budget_usage_tokens{service,model}` / `sec_groq_budget_remaining_tokens{service,model}` — Gauges tracking consumed versus remaining Groq token budgets.
- `sec_groq_budget_deferred_jobs_total{service,model}` — Counter of jobs deferred because the token budget was exhausted.

## Operational Notes

- The planner runs inside parser workers; backpressure guard (`QueueBackpressure`) stops chunk generation when backlog exceeds thresholds.
- Jobs are deduped by `job_id` (`<accession>:<section ordinal>:<chunk index>:<token>`). Stale acknowledgements are ignored to prevent task loss.
- To requeue a specific job manually:
  ```bash
  redis-cli srem ${CHUNK_QUEUE_NAME}:dedupe "<JOB_ID>"
  redis-cli rpush ${CHUNK_QUEUE_NAME} '{"job_id":"<JOB_ID>", ... }'
  ```
- Tests covering chunk planner (`backend/tests/test_chunk_planner.py`) and queue semantics (`backend/tests/test_chunk_queue.py`) should be updated whenever heuristics or payload shape changes.
- Token budgeting is enforced per service; once a daily budget is exceeded, workers defer jobs and leave them queued until the next window. Operators can raise limits via the env vars above or monitor `sec_groq_budget_remaining_tokens` to anticipate throttling.

## Section Summaries Worker

- `SectionSummaryService` consumes chunk jobs and calls Groq chat completions to produce bullet summaries per section chunk.
- Successful completions are persisted in `filing_analyses` with `analysis_type = section_chunk_summary`; tokens consumed feed the `sec_section_summary_tokens_total` counter.
- Retryable provider errors (429/5xx/timeouts) leave the message unacked so Redis requeues after the visibility timeout; fatal 4xx errors are acknowledged and logged.
- Metrics of interest:
  - `sec_section_summary_latency_seconds{model}`
  - `sec_section_summary_errors_total{stage}`
  - `sec_section_summary_completions_total{model}`

## Entity Extraction Worker

- `EntityExtractionService` consumes the dedicated entity queue (`ENTITY_QUEUE_NAME`) and produces structured entities (executive changes, guidance updates, litigation, covenants, related-party transactions, risk factor changes).
- Results are persisted in `filing_analyses` with `analysis_type = entity_extraction` and normalized into `filing_entities` (type, label, confidence, supporting excerpt, metadata).
- Parser workers fan out chunk jobs to both summary and entity queues; dedupe keys are unique per queue (`<job_id>:entity`).
- Retry/backoff semantics mirror the summarizer: retry on 429/5xx, acknowledge fatal 4xx or malformed responses.
- Metrics of interest:
  - `sec_entity_extraction_latency_seconds{model}`
  - `sec_entity_extraction_errors_total{stage}`
  - `sec_entity_extraction_entities_total{entity_type}`
