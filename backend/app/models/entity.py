"""Entity extraction models derived from SEC filings."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base

if TYPE_CHECKING:  # pragma: no cover - typing aid only
    from .analysis import FilingAnalysis
    from .filing import Filing, FilingSection


def _utcnow() -> datetime:
    return datetime.now(UTC)


class FilingEntity(Base):
    """Structured entity or intent extracted from a filing section."""

    __tablename__ = "filing_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_id: Mapped[int] = mapped_column(ForeignKey("filings.id"), nullable=False, index=True)
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("filing_sections.id"), nullable=True, index=True
    )
    analysis_id: Mapped[int | None] = mapped_column(
        ForeignKey("filing_analyses.id"), nullable=True, index=True
    )

    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    filing: Mapped[Filing] = relationship("Filing", back_populates="entities")
    section: Mapped[FilingSection | None] = relationship(
        "FilingSection", back_populates="entities"
    )
    analysis: Mapped[FilingAnalysis | None] = relationship(
        "FilingAnalysis", back_populates="entities"
    )

    def __repr__(self) -> str:
        excerpt = f"{self.source_excerpt[:30]}..." if self.source_excerpt else ""
        return (
            f"<FilingEntity(type={self.entity_type!r}, label={self.label!r}, "
            f"confidence={self.confidence}, excerpt={excerpt!r})>"
        )
