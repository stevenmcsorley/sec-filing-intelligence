#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "🔍 Frontend lint"
if [ -d "$repo_root/frontend/node_modules" ]; then
  (
    cd "$repo_root/frontend"
    npm run lint
  )
else
  echo "⚠️  Frontend dependencies not installed; skipping lint. Run 'npm install --prefix frontend --ignore-scripts'."
fi

echo "🐍 Backend lint"
if python3 - <<'PYCODE' >/dev/null 2>&1; then
import importlib.util
import sys

if importlib.util.find_spec("ruff") is None:
    sys.exit(1)
PYCODE
  (
    cd "$repo_root/backend"
    python3 -m ruff check .
  )
else
  echo "⚠️  Ruff is not installed; skipping backend lint. Install via 'pip install -r backend/requirements-dev.txt'."
fi
