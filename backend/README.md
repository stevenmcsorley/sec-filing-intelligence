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
