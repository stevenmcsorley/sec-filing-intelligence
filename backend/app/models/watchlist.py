"""Watchlist and watchlist items for ticker tracking."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base

if TYPE_CHECKING:
    from .organization import Organization


class Watchlist(Base):
    """User-defined watchlist of tickers for alert monitoring."""

    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(255), index=True, nullable=False
    )  # Keycloak subject UUID
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    organization: Mapped[Organization] = relationship("Organization", back_populates="watchlists")
    items: Mapped[list[WatchlistItem]] = relationship(
        "WatchlistItem", back_populates="watchlist", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Watchlist(id={self.id}, name={self.name!r}, user_id={self.user_id!r})>"


class WatchlistItem(Base):
    """Individual ticker in a watchlist."""

    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "ticker", name="uq_watchlist_ticker"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id"), nullable=False)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    watchlist: Mapped[Watchlist] = relationship("Watchlist", back_populates="items")

    def __repr__(self) -> str:
        return f"<WatchlistItem(watchlist_id={self.watchlist_id}, ticker={self.ticker!r})>"
