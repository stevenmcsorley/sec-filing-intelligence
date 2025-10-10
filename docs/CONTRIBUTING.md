# Contributing Guide

## Tooling Prerequisites

- Node.js ≥ 20.10 with Corepack (`corepack enable`) for the frontend workspace.
- Python ≥ 3.11 with `pip` or `uv` for backend services.
- Docker + Docker Compose for local orchestration.
- `pre-commit` (optional) for lint hooks if you prefer Python-native workflows.

## Branching & Commit Policy

- **Branch naming:** `<trello-id>/<slug>` (e.g., `TRELLO-001/repo-ci-scaffolding`).
- **Commits:** Follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/). Example:
  ```
  feat(frontend): add filings list route [TRELLO-004]
  ```
- **References:** Include the Trello card ID in every branch, commit, and PR title. This keeps the board, GitHub, and build log synchronized.

## Local Quality Gates

Use the `Makefile` targets to mirror CI checks:

```bash
make lint      # frontend lint + backend lint
make typecheck # frontend type-check + backend type-check (mypy placeholder)
make test      # frontend and backend unit tests
```

These commands invoke scripts under `scripts/ci/` and must pass before requesting review.

## Environment & Auth Bootstrap

- Copy `config/backend.env.example` and `config/keycloak.env.example` to `.env` counterparts before running Docker Compose.
- After the stack is up (`docker compose -f ops/compose/docker-compose.yml up -d`), import the Keycloak realm:
  ```bash
  ./ops/keycloak/seed-realm.sh
  ```
- The FastAPI app provides `/auth/health` and `/auth/me` for quick smoke tests against the Keycloak discovery endpoint and JWT verification pipeline.

## Commit Hooks & Conventional Commit Enforcement

Install repo-level dev dependencies:

```bash
npm install
```

This bootstraps Husky hooks:

- `commit-msg` → `npx commitlint --edit $1`
- `pre-commit` → `npx lint-staged`

If you prefer Python tooling, configure `pre-commit` to run `poetry run commitlint` or similar, but keep the same checks.

## Definition of Done (DoD)

Before moving a Trello card to **In Review**, ensure:

1. All acceptance criteria on the card are satisfied.
2. New code paths have automated tests (unit/integration/E2E as appropriate).
3. Documentation (README, runbooks, inline comments) reflects the change.
4. Secrets/config managed via `.env` (never in code or git history).
5. CI is green and the branch is rebased on latest `main`.

See `docs/DEFINITION_OF_DONE.md` for the detailed checklist.

## PR Checklist

- Pull Request template auto-populates the checklist. Do **not** remove Trello linkage.
- Request at least one reviewer with domain knowledge.
- Update `docs/BUILD_LOG.md` (or equivalent in Trello card comments) after merge to capture outcomes & deploy notes.
