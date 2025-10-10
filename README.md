# SEC Filing Intelligence Platform

This repository contains the monorepo for the SEC Filing Intelligence platform described in `PRD.md` and `StyleGuide.md`. The goal is to deliver a self-hosted system that ingests real filings from EDGAR, runs AI-driven analysis, and distributes tiered alerts with strict RBAC enforced via Keycloak and OPA.

## Repository Layout

- `frontend/` — Next.js 14 App Router frontend following the UI style guide.
- `backend/` — FastAPI service exposing ingestion, analysis orchestration, and alert APIs.
- `ops/compose/` — Docker Compose entrypoint for local orchestration.
- `ops/keycloak/` — Realm exports, seeding scripts, and documentation for Keycloak.
- `ops/opa/` — Policy bundles, Rego sources, and related tooling.
- `docs/` — Contributor onboarding, Definition of Done, runbooks, and Trello ↔ GitHub sync notes.
- `.github/` — CI pipelines, issue templates, CODEOWNERS, and PR process automation.
- `scripts/` — Shared CI helper scripts (lint, type-check, tests).

## Getting Started

1. Review `docs/CONTRIBUTING.md` for branch naming, Trello workflow, and conventional commit requirements.
2. Install the toolchains:
   - Node.js ≥ 20.10 (frontend) with Corepack enabled.
   - Python ≥ 3.11 (backend) with `uv` or `pip`.
   - Docker & Docker Compose (local orchestration).
3. Copy environment templates and adjust secrets:
   ```bash
   cp config/backend.env.example config/backend.env
   cp config/keycloak.env.example config/keycloak.env
   ```
4. Bootstrap dependencies:
   ```bash
   npm install     # installs root dev tooling (husky, commitlint)
   npm install --prefix frontend
   python -m pip install -r backend/requirements-dev.txt
   ```
5. Run local quality gates:
   ```bash
   make lint typecheck test
   ```

## Keycloak Bootstrap

The stack expects a Keycloak realm named `sec-intel` with clients (`frontend`, `backend`, `worker`, `grafana`) and tier roles. After starting the compose stack run:

```bash
docker compose -f ops/compose/docker-compose.yml up -d keycloak postgres
./ops/keycloak/seed-realm.sh
```

The helper script imports `ops/keycloak/realm-export/sec-intel-realm.json` using the admin credentials from `config/keycloak.env`.

FastAPI exposes `/auth/health` for checking the discovery endpoint and `/auth/me` for basic token introspection once Keycloak is running.

## Continuous Integration

GitHub Actions enforces linting, type-checking, and unit tests for both frontend and backend. Branch protection on `main` requires PR reviews and passing CI before merge (see Trello card `[TRELLO-001]`).

## Trello ↔ GitHub Workflow

All branches, commits, and PRs must reference the Trello card ID (e.g., `[TRELLO-001]`) to keep the build log synchronized. See `docs/TRELLO_SYNC.md` for the full checklist, including Build Log updates post-merge.
