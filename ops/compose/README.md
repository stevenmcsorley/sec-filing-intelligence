# Docker Compose Orchestration

This stack wires together the core services required for local development:

- FastAPI backend (with future Celery workers)
- Next.js frontend
- Postgres 16 for metadata storage
- Redis for task queues / caching
- MinIO for raw filing storage
- Keycloak for authentication/realm management
- OPA for authorization decisions

## Usage

```bash
# Ensure env files exist
cp config/backend.env.example config/backend.env
cp config/frontend.env.example config/frontend.env

# Build & launch
cd ops/compose
docker compose up --build
```

OPA policies and Keycloak realm exports are mounted from sibling directories (`../opa` and `../keycloak`). Populate them before running full auth flows.
