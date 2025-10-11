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

## Database & Migrations

### Schema Overview

The application uses PostgreSQL with SQLAlchemy ORM and Alembic for migrations. The schema includes:

- **companies**: SEC entities with CIK and ticker information
- **filings**: SEC filing metadata (10-K, 8-K, etc.) with processing status
- **filing_blobs**: Storage locations for raw/parsed content in MinIO
- **filing_sections**: Parsed sections with text content and hashes
- **organizations**: Multi-tenant organization entities
- **user_organizations**: User membership with roles (references Keycloak users)
- **subscriptions**: Subscription tiers and feature flags per organization
- **watchlists**: User-defined ticker watchlists for alert monitoring
- **watchlist_items**: Individual tickers within watchlists

### Running Migrations

**In Docker** (automatic on container start):
```bash
# Migrations run automatically via docker-entrypoint.sh
docker compose -f ops/compose/docker-compose.yml up -d backend
```

**Local Development**:
```bash
# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current migration version
alembic current

# Generate new migration (after model changes)
alembic revision --autogenerate -m "description"
```

### Seeding Test Data

The seed script creates a test organization with a free-tier subscription. No mock filing data is seeded (real filings are ingested from EDGAR).

**Via Docker**:
```bash
# Set SEED_DB=true in config/backend.env, then restart
docker compose -f ops/compose/docker-compose.yml restart backend
```

**Via CLI**:
```bash
python -m scripts.seed_db
```

### Database Configuration

Set in `config/backend.env`:
```bash
DATABASE_URL=postgresql+asyncpg://filings:filings@postgres:5432/filings
DATABASE_ECHO=false  # Set to true for SQL query logging
```

### Using the Database in Code

```python
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models import Company, Filing

router = APIRouter()

@router.get("/companies/{cik}")
async def get_company(
    cik: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    result = await db.execute(
        select(Company).where(Company.cik == cik)
    )
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(status_code=404)

    return {"cik": company.cik, "name": company.name}
```

### Testing with Database

Integration tests use an in-memory SQLite database for fast execution:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Company

@pytest.mark.asyncio
async def test_create_company(db_session: AsyncSession):
    company = Company(cik="0001234567", name="Test Corp")
    db_session.add(company)
    await db_session.commit()

    assert company.id is not None
```

See `backend/tests/test_models.py` for comprehensive examples.

## Authentication & Authorization

### Keycloak Integration

The backend uses Keycloak for authentication via OpenID Connect (OIDC):

- **JWT Verification**: All protected routes verify access tokens from Keycloak
- **Role Extraction**: User roles are extracted from token claims
- **Token Refresh**: Supports refresh token flows for long-lived sessions

**Configuration** (in `config/backend.env`):
```bash
KEYCLOAK_SERVER_URL=http://keycloak:8080
KEYCLOAK_REALM=sec-intel
KEYCLOAK_CLIENT_ID=backend
KEYCLOAK_AUDIENCE=backend
```

**Health Check**:
```bash
curl http://localhost:8000/auth/health
```

### OPA Integration

Authorization decisions are delegated to OPA (Open Policy Agent) for policy-driven access control:

- **Policy Evaluation**: Each protected action calls OPA to check permissions
- **Audit Logging**: All decisions are logged with full context for compliance
- **Configurable Policies**: Rego policies are mounted from `ops/opa/` directory

**Configuration** (in `config/backend.env`):
```bash
OPA_URL=http://opa:8181
```

**Testing OPA Integration**:
```bash
# Get a valid token first
TOKEN="<your-jwt-token>"

# Test permission check endpoint
curl "http://localhost:8000/auth/check-permission?action=alerts:view" \
  -H "Authorization: Bearer $TOKEN"
```

**Policy Development**:
1. Edit policies in `ops/opa/policy.rego`
2. Add test cases in `ops/opa/tests/policy_test.rego`
3. Run tests: `opa test ops/opa/policy.rego ops/opa/tests/policy_test.rego -v`
4. Reload: `docker compose restart opa`

**Troubleshooting**: See `docs/OPA_RUNBOOK.md` for common issues and solutions.

### Using OPA in Route Handlers

```python
from typing import Annotated
from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_token
from app.auth.opa import OPAClient, get_opa_client
from app.auth.router import token_to_user_context
from app.auth.models import TokenContext

router = APIRouter()

@router.get("/filings")
async def list_filings(
    token: Annotated[TokenContext, Depends(get_current_token)],
    opa_client: Annotated[OPAClient, Depends(get_opa_client)],
):
    # Convert token to OPA user context
    user_context = token_to_user_context(token)

    # Check permission
    decision = await opa_client.check_permission(
        user_context=user_context,
        action="filings:list",
        resource={"org_id": user_context["org_id"]}
    )

    if not decision.allow:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Proceed with authorized action
    return {"filings": [...]}
```

### Policy Input Schema

The OPA policy receives the following input structure:

```json
{
  "decision_id": "uuid-v4",
  "user": {
    "id": "user-sub-from-jwt",
    "email": "user@example.com",
    "roles": ["analyst_pro", "org_admin"],
    "subscription": {"tier": "pro"},
    "org_id": "org-123"
  },
  "action": "alerts:view",
  "resource": {
    "org_id": "org-123",
    "impact_score": 8.5
  }
}
```

### Current Policy Rules

- **Super Admin**: `super_admin` role allows all actions
- **Health Check**: `health:read` action is allowed for all authenticated users
- **Default**: All other actions are denied (allow-all will be extended in Phase 2)

See `ops/opa/policy.rego` for the complete policy definition.
