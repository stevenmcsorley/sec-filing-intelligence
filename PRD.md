PRD — SEC Filing Intelligence (Local, Dockerized, Keycloak + OPA)
1) Objective

Build a self-hosted platform that ingests real SEC filings, performs AI analysis to detect market-moving signals, and delivers tiered alerts. No mock/dummy data at any layer. For Phase 1, a Super Admin can see the entire system; Phase 2 introduces Keycloak roles + OPA policies to restrict views/actions by subscription.

2) Primary Users & Roles (Phase 1 → Phase 2)

Super Admin (Phase 1): Full visibility to all data/services, system settings, pipelines, logs, audit.

Org Admin: Manages org settings, billing (later), portfolios/watchlists for their org.

Analyst (Pro): Creates portfolios, receives real-time alerts, accesses advanced analytics.

Basic (Free): Limited tickers, delayed alerts, limited dashboards.

RBAC is enforced via Keycloak (authentication/roles) + OPA/Rego (resource-level authorization decisions). All role checks are policy-driven, not hardcoded.

3) Non-Goals (Phase 1)

Brokerage integrations (trading execution).

Mobile apps (responsive web only).

Public SaaS hosting (local deployment only).

Payments (Stripe) — stubbed interface only, no live billing yet.

4) Key Requirements
4.1 Data Ingestion (No Mock Data)

Source: SEC EDGAR official feeds (live).

Primary: Company and global filing feeds (RSS/Atom), plus the indexed bulk JSON where applicable.

Artifacts: 8-K, 10-K, 10-Q, S-1, 13D/G, 424B, NT filings, proxies, etc.

For each filing:

Persist metadata: cik, ticker, company name, form type, filing date/time, accession number, document URLs.

Persist raw content: download HTML/TXT/PDF into object storage.

Parse to clean text and sectionized chunks (MD&A, Risk Factors, Business, Notes, etc.) with robust HTML->text pipeline.

Idempotency: exactly-once ingest per accession number.

Backpressure: burst handling (heavy filing days).

4.2 AI Processing (Groq + Token Budget Guardrails)

LLM: Groq-hosted LLMs (e.g., Llama 3/Mixtral family).

Chunking: hierarchical chunking (by section → paragraphs → sentences); 2-pass summarization:

Section Summaries (parallel jobs, with token caps per job).

Global Synthesis (merge section signals into a concise filing brief).

Diff-aware: Compare new filing to the previous equivalent (e.g., 10-K vs prior 10-K) to extract changes.

Entity/Intent Extraction: detect specific catalysts (executive changes, guidance, litigation, restatements, covenants, related-party transactions, new risk factors).

Scoring:

Impact Score (High/Med/Low + numeric).

Confidence Score.

Category (Governance, Accounting, Legal, Strategy, Guidance).

Rate/Limit Management:

Job queue with concurrency limits per model and global QPS.

Token-budget planner (estimates tokens per job → schedules or defers).

Retries with exponential backoff; circuit breakers on provider errors.

4.3 Alerts & Subscriptions

Watchlists/Portfolios (per user/org): tickers, sectors, strategies.

Alert Rules:

Default: trigger on High/Medium impact.

Custom: form type filters, category filters, minimum confidence, delay windows.

Delivery (Phase 1): in-app notifications + email (local SMTP).

Free tier: limited tickers (e.g., 5), delayed alerts (e.g., +20 min), truncated analysis.

Pro tier: real-time, unlimited (or high cap) tickers, full analysis, diff views, historical analytics.

4.4 Authorization (Keycloak + OPA)

Keycloak:

Realms: sec-intel (single-tenant for now).

Clients: frontend, backend, worker, grafana (optional), admin-console.

Roles: super_admin, org_admin, analyst_pro, basic_free.

Groups for org membership; user attributes for subscription tier.

OPA/Rego:

Policy inputs: user.roles, user.org_id, resource.org_id, subscription.tier, alert.impact, feature_flags.

Example policies:

Super Admin: allow all.

Basic: alerts.view only on own org, only delayed alerts, limited ticker count, hide diff/advanced views.

Pro: broader limits, real-time, history access, diff viewers.

Decisions cached at edge (short TTL) with sidecar.

4.5 Observability, Audit, & Compliance

Audit: all admin and policy decisions logged (who/what/when, decision, inputs).

Metrics: ingestion lag, queue depth, token usage, error rates, alert latency.

Tracing: distributed traces across ingestion → AI → alerts.

Dashboards: Grafana (optional in Phase 1) for ops; in-app admin panels for product metrics.

4.6 Performance & Reliability Targets (MVP)

Ingestion → alert p50 < 2 min, p95 < 5 min (Pro).

99.5% successful ingestion/parse on supported filing types.

<0.1% duplicate alerts.

At-least-once alert delivery; idempotent notification handlers.

5) System Architecture (Dockerized)
5.1 Services

frontend: Next.js + Tailwind + shadcn/ui (OIDC with Keycloak).

api-gateway: FastAPI (or NestJS) REST/GraphQL; integrates with Keycloak (JWT) and calls OPA for authz.

ingestor: Periodic pollers for SEC feeds; pulls new filings; persists metadata; enqueues parse jobs.

parser: Converts HTML/TXT/PDF → canonical text; sectionizes; stores to object store + DB.

ai-orchestrator:

Builds chunk plans, enqueues Groq jobs (summaries, diffs, entity extraction).

Handles budget, concurrency, retries.

Persists AI outputs & scores.

signal-engine: Assigns impact/confidence, runs rule-based + ML heuristics, triggers alerts.

notifier: In-app + email delivery; templating; idempotency keys.

auth: Keycloak container.

policy: OPA sidecar (bundles Rego policies from a mounted volume).

db: PostgreSQL (+ pgvector).

queue: NATS or Redis (streams + delayed jobs).

objstore: MinIO (WORM optional later).

observability: Loki (logs), Prometheus, Grafana, OpenTelemetry collector (optional in MVP but recommended).

5.2 Data Model (high level)

companies(cik, ticker, name, sector, …)

filings(id, cik, ticker, form_type, filed_at, accession, source_urls, status)

filing_blobs(filing_id, kind: raw|text|sections, location: s3://…)

sections(id, filing_id, title, ordinal, text_vector, text_hash)

analyses(id, filing_id, section_id?, type: summary|diff|entities, content, tokens_used, scores)

alerts(id, filing_id, impact_score, confidence, categories[], created_at)

watchlists(id, org_id, name); watchlist_items(watchlist_id, ticker)

user_orgs(user_id, org_id, role); subscriptions(org_id, tier, features, limits)

policy_audit(decision_id, user_id, action, resource, allow, inputs, ts)

5.3 Docker Compose (outline)

Networks: app_net, data_net.

Volumes: pg_data, minio_data, loki_data, prom_data, grafana_data, opa_policies.

Secrets via .env + Docker secrets (Groq API key, SMTP creds).

No hardcoded credentials in images; all from env/secret mounts.

6) Security & Privacy

OIDC flows with PKCE; short-lived access tokens, refresh tokens managed by Keycloak.

OPA enforces least-privilege at API gateway.

All external calls (EDGAR, email) via egress allowlist.

PII minimal (email, name).

Signed, versioned OPA bundles; policy CI (unit tests for Rego).

Logs scrub secrets; audit logs immutable (optional: MinIO Object Lock later).

7) UX Flows
7.1 Super Admin (Phase 1)

System Dashboard: ingest lag, queue depths, errors, token budget, top filings by impact.

Filings Explorer: filter by date/form/ticker; view raw/parsed text; AI summaries; diffs; signals.

Alerts Monitor: stream of generated alerts; drill into AI reasoning and policies.

Auth/Policy: view assigned roles; test a policy decision with sample inputs.

Ops: retry failed jobs, re-parse, re-analyze, re-notify.

7.2 Analyst/Pro (Phase 2)

Create watchlists; set alert rules; receive real-time alerts; view historical impact + accuracy.

7.3 Basic/Free (Phase 2)

Add up to N tickers; get delayed alerts; limited detail view.

8) API (selected endpoints)

Auth/Me

GET /me → profile, roles, orgs, subscription (from Keycloak claims + DB).

Filings

GET /filings?form_type=&ticker=&from=&to=

GET /filings/{id} → metadata, links, sections availability.

GET /filings/{id}/analysis → summaries, entities, diff synopsis (OPA-gated by tier).

Alerts

GET /alerts?watchlist_id=&impact>=&from=&to=

POST /alerts/test (admin only) → simulate policy decision for a filing.

Watchlists

GET /watchlists (scoped to org via policy)

POST /watchlists / POST /watchlists/{id}/items

Admin/Ops

POST /admin/reparse/{filing_id}

POST /admin/reanalyze/{filing_id}

GET /admin/queues

GET /admin/policy/audit?from=&to=

All endpoints call OPA with { user_context, action, resource } for allow/deny + attribute filters (e.g., redact sections for Free).

9) AI Orchestration Details

Planner computes:

Chunk plan: section boundaries, max tokens per chunk, prioritization (e.g., MD&A > Risk Factors > Footnotes).

Budget: max tokens/job, max concurrent jobs; backoff if nearing provider limits.

Caching: content-hash keys → skip re-analysis for unchanged chunks.

Pipelines:

summarize_section → extract_entities → score_signals → synthesize_brief → diff_with_prior.

Quality Loop:

Human-in-the-loop feedback (thumbs up/down) for alert relevance; log outcomes.

Periodic evaluation: precision/recall of “market-moving” against post-filing price windows (T+1/T+5).

10) Limits & Quotas (by Tier)

Basic: up to 5 tickers/watchlist, 1 watchlist, delayed alerts (≥20min), no diff view, no export.

Pro: up to 200 tickers, real-time alerts, diffs, history, CSV export.

All enforced via OPA (feature flags + numerical limits in policy data).

11) Deployment & Operations

Local Docker Compose for all services.

Migrations via Alembic/Prisma (depending on backend).

One-click seed of config only (no mock data) — e.g., create default realm/roles in Keycloak, create OPA bundles, create admin account.

Health checks per service; readiness gates on DB/queue.

Backup: nightly Postgres + MinIO snapshots to local disk path.

12) Roadmap

MVP (2–3 weeks)

Ingestion (global feed), parse & store real filings.

AI orchestration with section summaries + basic signal scoring.

Alerts (in-app + email), watchlists.

Keycloak auth + Super Admin full system.

OPA wired (allow-all policy except Super Admin gating).

Observability basics: logs, metrics, queue dashboards.

Phase 2 (RBAC + Tiering)

Keycloak roles/groups; OPA policies for tiered access + feature flags.

Diff engine (prior filing vs current).

Historical analytics & accuracy reports.

Free vs Pro feature gating + delays.

Phase 3 (Scale & Polish)

Advanced heuristics/ML, sector models.

Performance hardening, backtesting, exports.

Stripe integration (local test mode), webhooks to update Keycloak roles/OPA data.

13) Acceptance Criteria (MVP)

✅ Ingest at least 100 real filings from live feeds within 24h; no duplicates.

✅ For each ingested filing, store raw + parsed text, at least 3 section summaries, and a final filing brief.

✅ Generate at least one alert per relevant 8-K detection rule (e.g., management change).

✅ Super Admin UI shows end-to-end pipeline status, retry controls, and audit logs.

✅ All secrets from env/secrets; no hardcoded values.

✅ Keycloak auth protects all APIs; OPA is in the decision path (even if permissive).

✅ Token budget cannot exceed configured limits; jobs queue without failure under burst of 200 filings.

Suggested Tech Choices (concrete)

Frontend: Next.js 14, React, Tailwind, shadcn/ui, OIDC client; Vite for local dev preview.

Backend: FastAPI (Python 3.11) — strong parsing/AI ecosystem; Pydantic; Uvicorn.

Workers: Celery (Redis broker) or Dramatiq; or NATS JetStream + FastAPI background workers.

DB: Postgres 16 + pgvector; SQLAlchemy + Alembic.

Obj Store: MinIO (S3 API).

Auth: Keycloak 25 (OIDC), Keycloak Gatekeeper/Envoy filter optional.

OPA: OPA sidecar with bundle mount; unit tests using opa test.

Observability: Prometheus, Loki, Grafana; OpenTelemetry SDK in services.

AI: Groq Python SDK (retry, rate caps, token estimator), local embedding model (e.g., all-MiniLM) or Groq embeddings if available.

Parsing: trafilatura/readability-lxml + custom cleaners; pdfminer for PDFs.

Rego Policy Sketch (illustrative)
package authz

default allow = false

is_super_admin {
  "super_admin" in input.user.roles
}

allow {
  is_super_admin
}

allow {
  input.action == "alerts:view"
  input.resource.org_id == input.user.org_id
  some tier
  tier := input.user.subscription.tier
  tier == "pro"
}

allow {
  input.action == "alerts:view"
  input.resource.org_id == input.user.org_id
  input.user.subscription.tier == "free"
  # Free users: only delayed alerts
  time.now_ns() - input.resource.created_at_ns > input.policy.free_delay_ns
}