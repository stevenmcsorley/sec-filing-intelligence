#!/bin/bash
set -e

echo "🔄 Running database migrations..."
alembic upgrade head

if [ "$?" -eq 0 ]; then
    echo "✅ Database migrations completed successfully"
else
    echo "❌ Database migrations failed"
    exit 1
fi

# Optionally seed database (only if SEED_DB env var is set)
if [ "$SEED_DB" = "true" ]; then
    echo "🌱 Seeding database..."
    python -m scripts.seed_db
    if [ "$?" -eq 0 ]; then
        echo "✅ Database seeding completed successfully"
    else
        echo "❌ Database seeding failed"
        exit 1
    fi
fi

echo "🚀 Starting application..."
exec "$@"
