"""Database connection and session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import Settings, get_settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


# Global engine and session maker (initialized on startup)
_engine = None
_async_session_maker = None


def init_db(settings: Settings) -> None:
    """Initialize database engine and session maker.

    Called during FastAPI startup event.
    """
    global _engine, _async_session_maker

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

    _async_session_maker = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def close_db() -> None:
    """Close database connections.

    Called during FastAPI shutdown event.
    """
    global _engine
    if _engine:
        await _engine.dispose()


async def get_db_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Usage:
        @router.get("/items")
        async def list_items(db: Annotated[AsyncSession, Depends(get_db_session)]):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    if _async_session_maker is None:
        init_db(settings)

    async with _async_session_maker() as session:  # type: ignore[misc]
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
