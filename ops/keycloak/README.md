# Keycloak Realm Bootstrap

This directory stores exported realm configuration for the `sec-intel` realm.

## Target State

- Clients: `frontend`, `backend`, `worker`, `grafana`.
- Roles: `super_admin`, `org_admin`, `analyst_pro`, `basic_free`.
- Groups: organization membership scaffolding.

## Local Workflow

1. Launch Keycloak via `docker compose` (see `ops/compose`).
2. Run `./scripts/keycloak/export.sh` (to be implemented) to export the realm to `realm-export/`.
3. Commit sanitized exports (remove secrets, user PII).
4. Document admin credentials and default accounts in `docs/` (never check secrets into git).

Upcoming Trello cards will replace this README with concrete seeding scripts and automation.
