# End-to-End Smoke Test Guide

This guide validates the complete Keycloak + OPA + Backend integration stack from service startup to authenticated, authorized API requests.

## Objective

Verify that:
1. All services (Keycloak, OPA, Backend, Postgres, Redis) start successfully
2. Keycloak realm is seeded with roles and test users
3. JWT tokens can be obtained and verified
4. OPA policy decisions are correctly enforced on protected routes
5. Audit logging captures authorization decisions

## Prerequisites

- Docker & Docker Compose installed
- Environment files configured (backend, keycloak)
- No services running on ports: 8000, 8080, 8181, 5432, 6379

## Test Procedure

### 1. Environment Setup

```bash
# Copy environment templates
cp config/backend.env.example config/backend.env
cp config/keycloak.env.example config/keycloak.env
cp config/frontend.env.example config/frontend.env

# Ensure Keycloak admin credentials are set in config/keycloak.env
# KEYCLOAK_ADMIN=admin
# KEYCLOAK_ADMIN_PASSWORD=admin
```

### 2. Start Services

```bash
# Start all services in background
docker compose -f ops/compose/docker-compose.yml up -d

# Verify all containers are running
docker compose -f ops/compose/docker-compose.yml ps

# Expected output: backend, frontend, postgres, redis, minio, keycloak, opa all "Up"
```

**Wait ~30 seconds** for Keycloak to fully initialize.

### 3. Bootstrap Keycloak Realm

```bash
# Seed the sec-intel realm with roles and test users
./ops/keycloak/seed-realm.sh

# Expected output:
# ✅ Realm 'sec-intel' imported successfully
# ✅ Test users created: admin@test.com, analyst@test.com, basic@test.com
```

**Verify realm import:**
```bash
# Check Keycloak logs for successful realm import
docker compose -f ops/compose/docker-compose.yml logs keycloak | grep "sec-intel"
```

### 4. Verify Backend Health

```bash
# Check backend is up and running
curl http://localhost:8000/health

# Expected: {"status":"ok"}
```

**Check auth health (Keycloak discovery):**
```bash
curl http://localhost:8000/auth/health

# Expected: {"status":"ok"}
# This confirms backend can reach Keycloak's OIDC discovery endpoint
```

### 5. Verify OPA Health

```bash
# Check OPA is responding
curl http://localhost:8181/health

# Expected: {} (empty JSON means healthy)
```

**Test OPA policy directly:**
```bash
curl -X POST http://localhost:8181/v1/data/authz/allow \
  -H 'Content-Type: application/json' \
  -d '{
    "input": {
      "decision_id": "smoke-test-1",
      "user": {
        "id": "test-admin",
        "roles": ["super_admin"]
      },
      "action": "any:action",
      "resource": {}
    }
  }'

# Expected: {"result": true}
```

### 6. Obtain JWT Token

**Option A: Direct Keycloak Token Endpoint** (Recommended for smoke tests)

```bash
# Get token for super_admin test user
TOKEN=$(curl -X POST http://localhost:8080/realms/sec-intel/protocol/openid-connect/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=password' \
  -d 'client_id=backend' \
  -d 'username=admin@test.com' \
  -d 'password=admin123' \
  | jq -r '.access_token')

# Verify token was obtained
echo $TOKEN | cut -c1-50
# Should output: eyJhbGciOiJSUzI1NiIsInR5cCI... (JWT header)
```

**Option B: Manual Browser Flow** (UI verification)

1. Navigate to: `http://localhost:8080/realms/sec-intel/account`
2. Login with: `admin@test.com` / `admin123`
3. Use browser dev tools to capture the token from cookies/localStorage

### 7. Test JWT Verification

```bash
# Call /auth/me with the token
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"

# Expected output:
# {
#   "sub": "...",
#   "email": "admin@test.com",
#   "roles": ["super_admin", "org_admin"],
#   "exp": 1234567890
# }
```

**Negative test (invalid token):**
```bash
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer invalid-token"

# Expected: HTTP 401 Unauthorized
# {"detail": "Invalid token"}
```

### 8. Test OPA Authorization Integration

**Test 1: Super Admin - Should Allow All Actions**

```bash
curl "http://localhost:8000/auth/check-permission?action=admin:delete_all" \
  -H "Authorization: Bearer $TOKEN"

# Expected:
# {
#   "allow": true,
#   "audit_log": {
#     "decision_id": "...",
#     "user": {...},
#     "action": "admin:delete_all",
#     "allowed": true
#   }
# }
```

**Test 2: Health Check - Should Allow for All Users**

```bash
# Get token for basic user
BASIC_TOKEN=$(curl -X POST http://localhost:8080/realms/sec-intel/protocol/openid-connect/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=password' \
  -d 'client_id=backend' \
  -d 'username=basic@test.com' \
  -d 'password=basic123' \
  | jq -r '.access_token')

curl "http://localhost:8000/auth/check-permission?action=health:read" \
  -H "Authorization: Bearer $BASIC_TOKEN"

# Expected:
# {
#   "allow": true,
#   "audit_log": {...}
# }
```

**Test 3: Unauthorized Action - Should Deny**

```bash
curl "http://localhost:8000/auth/check-permission?action=admin:delete" \
  -H "Authorization: Bearer $BASIC_TOKEN"

# Expected:
# {
#   "allow": false,
#   "audit_log": {
#     "decision_id": "...",
#     "allowed": false
#   }
# }
```

### 9. Verify OPA Decision Logging

```bash
# Check OPA container logs for decision logs
docker compose -f ops/compose/docker-compose.yml logs opa | tail -20

# Expected: JSON decision logs with input/result for each check-permission call
# Look for: "decision_id", "input", "result", "timestamp"
```

### 10. Verify Backend Audit Logging

```bash
# Check backend logs for OPA decision entries
docker compose -f ops/compose/docker-compose.yml logs backend | grep "OPA decision"

# Expected: Structured log entries with:
# - decision_id
# - action
# - allow (true/false)
# - user_id
# - roles
```

## Expected Results Summary

| Test | Endpoint/Action | Expected Result |
|------|----------------|-----------------|
| Backend health | GET /health | `{"status":"ok"}` |
| Auth health | GET /auth/health | `{"status":"ok"}` |
| OPA health | GET /health (OPA) | `{}` |
| Token obtain | Keycloak /token | Valid JWT token |
| Token verify | GET /auth/me | User profile with roles |
| Super admin access | check-permission (admin action) | `allow: true` |
| Basic user health | check-permission (health:read) | `allow: true` |
| Basic user restricted | check-permission (admin action) | `allow: false` |
| OPA logs | docker logs opa | Decision logs present |
| Backend logs | docker logs backend | Audit logs present |

## Troubleshooting

### Services won't start

```bash
# Check for port conflicts
lsof -i :8000 -i :8080 -i :8181 -i :5432 -i :6379

# View service logs
docker compose -f ops/compose/docker-compose.yml logs <service-name>
```

### Keycloak realm import fails

```bash
# Check realm export exists
ls -l ops/keycloak/realm-export/sec-intel-realm.json

# Verify Keycloak is fully started (wait for "Running the server")
docker compose -f ops/compose/docker-compose.yml logs keycloak | grep "Running"

# Manual realm import via Admin Console
# Navigate to: http://localhost:8080/admin/master/console
# Login: admin/admin
# Realm → Create Realm → Import ops/keycloak/realm-export/sec-intel-realm.json
```

### Token exchange fails (401/403)

```bash
# Verify Keycloak client configuration
# Check that client_id='backend' exists in realm
# Ensure Direct Access Grants are enabled for the client

# Test credentials manually in Keycloak admin console
http://localhost:8080/admin/master/console/#/sec-intel/users
```

### OPA returns unexpected decisions

```bash
# Test policy directly with known input
curl -X POST http://localhost:8181/v1/data/authz \
  -H 'Content-Type: application/json' \
  -d '{"input": {...}}' | jq

# Run Rego policy tests
docker compose -f ops/compose/docker-compose.yml exec opa \
  opa test /policies/policy.rego /policies/tests/policy_test.rego -v

# Check policy syntax
docker compose -f ops/compose/docker-compose.yml exec opa \
  opa check /policies/policy.rego
```

### Backend can't reach OPA/Keycloak

```bash
# Verify services are on same Docker network
docker network inspect ops_compose_secnet

# Test connectivity from backend container
docker compose -f ops/compose/docker-compose.yml exec backend ping opa
docker compose -f ops/compose/docker-compose.yml exec backend ping keycloak

# Check environment variables
docker compose -f ops/compose/docker-compose.yml exec backend env | grep -E "OPA_URL|KEYCLOAK"
```

## Cleanup

```bash
# Stop all services
docker compose -f ops/compose/docker-compose.yml down

# Remove volumes (full reset)
docker compose -f ops/compose/docker-compose.yml down -v
```

## Next Steps

After smoke tests pass:

1. **Create test users with different roles** (org_admin, analyst_pro, basic_free)
2. **Extend OPA policies** for tier-based access (Phase 2)
3. **Implement real org_id and subscription.tier** lookup (replace stubs in `token_to_user_context`)
4. **Add integration tests** that spin up the stack via testcontainers
5. **Monitor decision latency** and add caching if needed

## Related Documentation

- [OPA Runbook](OPA_RUNBOOK.md) - Troubleshooting OPA issues
- [Backend README](../backend/README.md) - Auth integration details
- [Keycloak Setup](../ops/keycloak/README.md) - Realm configuration

---

**Last Updated:** 2025-10-11
**Validated Against:** [TRELLO-002], [TRELLO-003]
**Maintained By:** Platform Team
