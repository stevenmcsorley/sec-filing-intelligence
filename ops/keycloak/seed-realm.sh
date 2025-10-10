#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_FILE="$PROJECT_ROOT/compose/docker-compose.yml"
KEYCLOAK_ENV_PATH=${KEYCLOAK_ENV_PATH:-$PROJECT_ROOT/../config/keycloak.env}
REALM_FILE=${REALM_FILE:-/realm-export/sec-intel-realm.json}
KEYCLOAK_CONTAINER=${KEYCLOAK_CONTAINER:-keycloak}
KEYCLOAK_SERVER_URL_INSIDE=${KEYCLOAK_SERVER_URL_INSIDE:-http://localhost:8080}

load_env_file() {
  local env_source="$1"
  if [[ -f "$env_source" ]]; then
    # shellcheck disable=SC1090
    set -o allexport
    source "$env_source"
    set +o allexport
    return 0
  fi
  return 1
}

# Prefer user-provided env overrides, fallback to example to avoid unset vars during local bootstrapping.
load_env_file "$KEYCLOAK_ENV_PATH" || load_env_file "$PROJECT_ROOT/../config/keycloak.env.example" || true

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

# Ensure Keycloak is reachable before attempting to seed.
echo "Checking Keycloak availability..."
compose exec "$KEYCLOAK_CONTAINER" /opt/keycloak/bin/kcadm.sh config credentials \
  --server "$KEYCLOAK_SERVER_URL_INSIDE" \
  --realm master \
  --user "${KEYCLOAK_ADMIN:-admin}" \
  --password "${KEYCLOAK_ADMIN_PASSWORD:-admin}" >/dev/null

echo "Seeding realm data from $REALM_FILE..."
if compose exec "$KEYCLOAK_CONTAINER" /opt/keycloak/bin/kcadm.sh get realms/sec-intel >/dev/null 2>&1; then
  echo "Realm 'sec-intel' already exists; skipping import."
else
  compose exec "$KEYCLOAK_CONTAINER" /opt/keycloak/bin/kcadm.sh create realms -f "$REALM_FILE"
  echo "Realm 'sec-intel' imported."
fi
