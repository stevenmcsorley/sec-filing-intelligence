"""Organization, user membership, and subscription models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base

if TYPE_CHECKING:
    from .watchlist import Watchlist


class Organization(Base):
    """Organization (tenant) for multi-tenancy support."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    user_memberships: Mapped[list[UserOrganization]] = relationship(
        "UserOrganization", back_populates="organization", cascade="all, delete-orphan"
    )
    subscription: Mapped[Subscription | None] = relationship(
        "Subscription", back_populates="organization", uselist=False
    )
    watchlists: Mapped[list[Watchlist]] = relationship(
        "Watchlist", back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organization(slug={self.slug!r}, name={self.name!r})>"


class UserOrganization(Base):
    """Many-to-many mapping between users and organizations with roles.

    Note: user_id references Keycloak subject (UUID string), not a local users table.
    """

    __tablename__ = "user_organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(255), index=True, nullable=False
    )  # Keycloak subject UUID
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # org_admin, analyst_pro, basic_free
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="user_memberships"
    )

    def __repr__(self) -> str:
        return (
            f"<UserOrganization(user_id={self.user_id!r}, "
            f"org_id={self.organization_id}, role={self.role!r})>"
        )


class Subscription(Base):
    """Subscription tier and feature flags for an organization."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), unique=True, nullable=False
    )
    tier: Mapped[str] = mapped_column(String(20), nullable=False)  # free, pro, enterprise
    features: Mapped[str | None] = mapped_column(Text)  # JSON object with feature flags
    limits: Mapped[str | None] = mapped_column(Text)  # JSON object with limits (max_tickers, etc)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    organization: Mapped[Organization] = relationship("Organization", back_populates="subscription")

    def __repr__(self) -> str:
        return f"<Subscription(org_id={self.organization_id}, tier={self.tier!r})>"
