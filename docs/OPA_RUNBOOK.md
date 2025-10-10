# OPA Troubleshooting Runbook

This runbook provides guidance for diagnosing and resolving OPA (Open Policy Agent) authorization issues in the SEC Filing Intelligence platform.

## Quick Health Check

### 1. Verify OPA is Running

```bash
# Check OPA container status
docker compose -f ops/compose/docker-compose.yml ps opa

# Check OPA health endpoint
curl http://localhost:8181/health
```

Expected response: `{}`

### 2. Test Policy Evaluation

```bash
# Test a simple policy decision
curl -X POST http://localhost:8181/v1/data/authz/allow \
  -H 'Content-Type: application/json' \
  -d '{
    "input": {
      "decision_id": "test-123",
      "user": {
        "id": "admin",
        "roles": ["super_admin"]
      },
      "action": "any:action",
      "resource": {}
    }
  }'
```

Expected response: `{"result": true}`

### 3. Run Policy Unit Tests

```bash
# Execute Rego tests locally
opa test ops/opa/policy.rego ops/opa/tests/policy_test.rego -v

# Or run in container
docker exec $(docker compose -f ops/compose/docker-compose.yml ps -q opa) \
  opa test /policies/policy.rego /policies/tests/policy_test.rego -v
```

## Common Issues

### Issue 1: Backend Returns 503 "Authorization service unavailable"

**Symptoms:**
- API requests fail with HTTP 503
- Backend logs show "OPA timeout" or connection errors

**Diagnosis:**
```bash
# Check OPA container logs
docker compose -f ops/compose/docker-compose.yml logs opa

# Verify network connectivity from backend
docker compose -f ops/compose/docker-compose.yml exec backend ping opa
```

**Resolution:**
1. Ensure OPA container is running: `docker compose up -d opa`
2. Check `OPA_URL` in `config/backend.env` points to `http://opa:8181`
3. Verify both services are on the same Docker network (`secnet`)
4. Restart backend if OPA was restarted: `docker compose restart backend`

### Issue 2: Unexpected 403 "Insufficient permissions"

**Symptoms:**
- Valid users are denied access
- Audit logs show `"allowed": false` for expected actions

**Diagnosis:**
```bash
# Query the decision with input details
curl -X POST http://localhost:8181/v1/data/authz \
  -H 'Content-Type: application/json' \
  -d '{
    "input": {
      "decision_id": "debug-001",
      "user": {
        "id": "user-123",
        "roles": ["analyst_pro"],
        "subscription": {"tier": "pro"},
        "org_id": "org-456"
      },
      "action": "alerts:view",
      "resource": {"org_id": "org-456"}
    }
  }'

# Check audit log output
curl -X POST http://localhost:8181/v1/data/authz/audit_log \
  -H 'Content-Type: application/json' \
  -d '<same input as above>'
```

**Resolution:**
1. Verify user roles are correctly assigned in Keycloak
2. Check that the action name matches exactly (case-sensitive)
3. Ensure `input.user.roles` contains expected role strings
4. Review policy logic in `ops/opa/policy.rego`
5. Add debug logging: `print(input)` in Rego and check OPA container logs

### Issue 3: Policy Changes Not Taking Effect

**Symptoms:**
- Updated Rego policies don't change decisions
- New rules are ignored

**Diagnosis:**
```bash
# Check mounted policy files in container
docker compose -f ops/compose/docker-compose.yml exec opa ls -la /policies

# Verify policy content
docker compose -f ops/compose/docker-compose.yml exec opa cat /policies/policy.rego
```

**Resolution:**
1. OPA watches mounted volumes automatically, but verify mounts in `docker-compose.yml`:
   ```yaml
   volumes:
     - ../opa:/policies
   ```
2. Restart OPA container to force reload:
   ```bash
   docker compose -f ops/compose/docker-compose.yml restart opa
   ```
3. Check for Rego syntax errors:
   ```bash
   opa check ops/opa/policy.rego
   ```

### Issue 4: Audit Logs Missing or Incomplete

**Symptoms:**
- `audit_log` field is `null` in decisions
- Missing decision context in logs

**Diagnosis:**
```bash
# Enable OPA decision logging
docker compose -f ops/compose/docker-compose.yml logs opa | grep decision

# Check if audit_log rule exists
curl http://localhost:8181/v1/data/authz/audit_log \
  -X POST -H 'Content-Type: application/json' \
  -d '{"input": {...}}'
```

**Resolution:**
1. Verify `audit_log` rule is defined in `ops/opa/policy.rego`
2. Ensure backend queries both `/authz/allow` and `/authz/audit_log`
3. Check backend logs for errors in `OPAClient.check_permission()`
4. Validate audit log structure matches `OPADecision.audit_log` schema

### Issue 5: Performance Degradation / High Latency

**Symptoms:**
- Slow API responses (>500ms)
- OPA CPU usage high

**Diagnosis:**
```bash
# Check OPA container resources
docker stats $(docker compose -f ops/compose/docker-compose.yml ps -q opa)

# Enable OPA profiling
docker compose -f ops/compose/docker-compose.yml exec opa \
  opa run --server --diagnostic-addr=:8282 /policies
```

**Resolution:**
1. Review policy complexity (avoid heavy loops, recursion)
2. Implement backend-side caching with short TTL (60s):
   ```python
   # In OPAClient, add caching layer
   from functools import lru_cache
   ```
3. Pre-compute expensive policy data in `ops/opa/data/*.json`
4. Consider OPA bundle optimization for large policy sets

## Policy Development Workflow

### Adding a New Policy Rule

1. **Edit policy:**
   ```bash
   vim ops/opa/policy.rego
   ```

2. **Write test cases:**
   ```bash
   vim ops/opa/tests/policy_test.rego
   ```

3. **Run tests locally:**
   ```bash
   opa test ops/opa/policy.rego ops/opa/tests/policy_test.rego -v
   ```

4. **Reload in dev environment:**
   ```bash
   docker compose -f ops/compose/docker-compose.yml restart opa
   ```

5. **Test via API:**
   ```bash
   curl http://localhost:8000/auth/check-permission?action=new:action \
     -H "Authorization: Bearer $TOKEN"
   ```

### Extending Policy Data

1. **Add tier/feature config:**
   ```bash
   vim ops/opa/data/tiers.json
   vim ops/opa/data/feature_flags.json
   ```

2. **Reference in policy:**
   ```rego
   import data.tiers
   import data.feature_flags

   allow {
       tier := data.tiers[input.user.subscription.tier]
       tier.features.real_time_alerts == true
   }
   ```

3. **Restart OPA** to load new data files.

## Monitoring & Observability

### Key Metrics to Track

- **Decision latency** (p50, p95, p99)
- **Allow vs Deny ratio** per action
- **OPA request rate** (qps)
- **Error rate** (timeouts, 500s)

### Logging Best Practices

1. **Backend logs** (`app/auth/opa.py`):
   - Log decision_id, user_id, action, allow/deny
   - Use structured logging (JSON format)

2. **OPA decision logs** (enabled via `--set=decision_logs.console=true`):
   - Review for policy evaluation traces
   - Check input/output mismatches

3. **Audit trail**:
   - Store `audit_log` in database for compliance
   - Include timestamp, IP, user agent

## Emergency Procedures

### Bypass OPA (Emergency Only)

If OPA is completely down and blocking all traffic:

1. **Temporary fix** - Comment out OPA check in critical routes:
   ```python
   # In backend/app/auth/router.py
   # decision = await opa_client.check_permission(...)
   # Temporarily allow all
   ```

2. **Redeploy backend** with emergency bypass

3. **Fix OPA** and restore normal flow

4. **Audit** all actions during bypass period

### Rollback Policy Changes

```bash
# View policy history
git log --oneline ops/opa/policy.rego

# Rollback to previous version
git checkout <commit-hash> ops/opa/policy.rego

# Restart OPA
docker compose -f ops/compose/docker-compose.yml restart opa
```

## Support Escalation

1. **Check decision logs** - Export last 100 decisions for analysis
2. **Run `opa test`** - Verify all tests pass
3. **Capture full input/output** - Use `/v1/data/authz` for complete evaluation
4. **Review Rego semantics** - Consult [OPA docs](https://www.openpolicyagent.org/docs/latest/)

---

**Last Updated:** 2025-10-10
**Maintained By:** Platform Team
**Related:** `docs/CONTRIBUTING.md`, `PRD.md`, `ops/opa/README.md`
