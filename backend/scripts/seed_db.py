"""Seed database with test organizations and subscription tiers.

This script creates:
- A test organization with default subscription
- No mock filing data (real filings will be ingested from EDGAR)

Usage:
    python -m scripts.seed_db
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.config import get_settings
from app.db import init_db
from app.models import Organization, Subscription
from sqlalchemy import select


async def seed_database() -> None:
    """Seed the database with test data."""
    settings = get_settings()
    init_db(settings)

    # Import after init_db to ensure engine is available
    from app.db import _async_session_maker

    if _async_session_maker is None:
        raise RuntimeError("Database not initialized")

    async with _async_session_maker() as session:
        # Check if test org already exists
        result = await session.execute(
            select(Organization).where(Organization.slug == "test-org")
        )
        existing_org = result.scalar_one_or_none()

        if existing_org:
            print("✅ Test organization already exists")
            return

        # Create test organization
        test_org = Organization(
            name="Test Organization",
            slug="test-org",
            created_at=datetime.now(UTC),
        )
        session.add(test_org)
        await session.flush()  # Get the ID

        # Create free tier subscription
        subscription = Subscription(
            organization_id=test_org.id,
            tier="free",
            features='{"real_time_alerts": false, "diff_view": false, "csv_export": false}',
            limits='{"max_tickers": 5, "max_watchlists": 1, "alert_delay_seconds": 1200}',
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(subscription)

        await session.commit()
        print(f"✅ Created test organization: {test_org.slug} (ID: {test_org.id})")
        print(f"✅ Created free tier subscription (ID: {subscription.id})")


async def main() -> None:
    """Main entry point."""
    try:
        await seed_database()
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
