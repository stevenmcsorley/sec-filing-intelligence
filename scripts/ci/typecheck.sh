#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "🧪 Frontend type-check"
if [ -d "$repo_root/frontend/node_modules" ]; then
  (
    cd "$repo_root/frontend"
    npm run typecheck
  )
else
  echo "⚠️  Frontend dependencies not installed; skipping type-check. Run 'npm install --prefix frontend --ignore-scripts'."
fi

echo "🧪 Backend type-check"
if command -v mypy >/dev/null 2>&1; then
  (
    cd "$repo_root/backend"
    mypy app
  )
else
  echo "⚠️  mypy is not installed; skipping backend type-check. Install via 'pip install -r backend/requirements-dev.txt'."
fi
