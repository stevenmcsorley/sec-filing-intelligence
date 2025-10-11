import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest_asyncio
from app.db import Base

# Import models to register them with Base.metadata
from app.models import (  # noqa: F401
    Company,
    Filing,
    FilingAnalysis,
    FilingBlob,
    FilingEntity,
    FilingSection,
    Organization,
    Subscription,
    UserOrganization,
    Watchlist,
    WatchlistItem,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with in-memory SQLite.

    Each test gets a fresh database with all tables created.
    """
    # Use in-memory SQLite for fast tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Provide session to test
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            # Test raised an exception, rollback
            await session.rollback()
            raise
        else:
            # Test completed successfully, try to commit
            try:
                await session.commit()
            except Exception:
                # Commit failed (e.g., transaction already rolled back in test)
                await session.rollback()

    # Cleanup
    await engine.dispose()
