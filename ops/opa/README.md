# OPA Policy Bundle

Bootstrap Rego policies for the SEC Filing Intelligence authorization layer.

## Structure

- `policy.rego` — root package `authz`, currently permit-all with audit logging hooks.
- `data/` — JSON data documents (tiers, feature flags, limits); add sanitized samples only.
- `tests/` — Rego unit tests executed via `opa test`.

## Local Workflow

1. Modify policies under `ops/opa`.
2. Run `opa test ./...` locally.
3. Mount this directory into the OPA container via Docker Compose.

Upcoming Trello cards will introduce concrete policies derived from `PRD.md` acceptance criteria.
