"""Company model for SEC entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base

if TYPE_CHECKING:
    from .filing import Filing


class Company(Base):
    """SEC company/entity with CIK and ticker information.

    Represents an SEC-registered entity that files reports.
    """

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    cik: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(10), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))

    # Relationships
    filings: Mapped[list[Filing]] = relationship(
        "Filing", back_populates="company", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Company(cik={self.cik!r}, ticker={self.ticker!r}, name={self.name!r})>"
