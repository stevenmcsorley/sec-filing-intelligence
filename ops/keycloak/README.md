# Keycloak Realm Bootstrap

This directory provides the declarative assets and tooling required to seed the `sec-intel` realm locally.

## Artifacts

- `realm-export/sec-intel-realm.json` — sanitized realm export including required clients and realm roles.
- `seed-realm.sh` — helper script that uses `kcadm.sh` (Keycloak admin CLI) to import/update the realm.

## Usage

1. Copy `config/keycloak.env.example` to `config/keycloak.env` and adjust the admin credentials before starting the stack.
2. Start the compose stack:  
   ```bash
   cd ops/compose
   docker compose up -d keycloak postgres
   ```
3. Once Keycloak is listening on port 8080, seed (or update) the realm:
   ```bash
   ./ops/keycloak/seed-realm.sh
   ```
   The script is idempotent — if the realm already exists it skips recreation.

## Realm Contents

- Clients: `frontend`, `backend`, `worker`, `grafana`.
- Realm roles: `super_admin`, `org_admin`, `analyst_pro`, `basic_free`.
- Default group `default-org` with the `basic_free` role attached.

Never commit real credentials or user exports. Keep all secrets in `config/keycloak.env` (ignored by git).
