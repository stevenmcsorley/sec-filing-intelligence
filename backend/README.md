# Backend Service

FastAPI application responsible for ingest pipelines, AI orchestration, and alert delivery APIs.

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

## Quality Gates

- `python -m ruff check .` — linting (enforced in CI).
- `mypy app` — static type checks.
- `pytest` — unit tests (includes API smoke tests).

OPA and Keycloak integration stubs will be added in upcoming Trello cards; see `docs/CONTRIBUTING.md` for workflow details.
