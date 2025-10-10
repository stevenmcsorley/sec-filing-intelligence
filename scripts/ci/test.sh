#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "🧪 Frontend tests"
if [ -d "$repo_root/frontend/node_modules" ]; then
  (
    cd "$repo_root/frontend"
    npm run test
  )
else
  echo "⚠️  Frontend dependencies not installed; skipping frontend tests. Run 'npm install --prefix frontend --ignore-scripts'."
fi

echo "🧪 Backend tests"
if command -v pytest >/dev/null 2>&1; then
  (
    cd "$repo_root/backend"
    pytest
  )
else
  echo "⚠️  pytest is not installed; skipping backend tests. Install via 'pip install -r backend/requirements-dev.txt'."
fi
