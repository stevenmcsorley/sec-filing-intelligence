"""Diff metadata models comparing sequential SEC filings."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base

if TYPE_CHECKING:  # pragma: no cover - typing aid only
    from .analysis import FilingAnalysis
    from .filing import Filing, FilingSection


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DiffStatus(str, Enum):
    """Processing status for filing diffs."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class FilingDiff(Base):
    """Represents a diff run between the latest filing and the prior equivalent."""

    __tablename__ = "filing_diffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    current_filing_id: Mapped[int] = mapped_column(
        ForeignKey("filings.id"), unique=True, nullable=False
    )
    previous_filing_id: Mapped[int] = mapped_column(
        ForeignKey("filings.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default=DiffStatus.PENDING.value, index=True)
    expected_sections: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_sections: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    current_filing: Mapped[Filing] = relationship(
        "Filing",
        foreign_keys=[current_filing_id],
        back_populates="diff_from_previous",
    )
    previous_filing: Mapped[Filing] = relationship(
        "Filing",
        foreign_keys=[previous_filing_id],
        back_populates="diffs_as_previous",
    )
    section_diffs: Mapped[list[FilingSectionDiff]] = relationship(
        "FilingSectionDiff",
        back_populates="filing_diff",
        cascade="all, delete-orphan",
        order_by="FilingSectionDiff.section_ordinal",
    )

    def __repr__(self) -> str:
        return (
            f"<FilingDiff(current_filing_id={self.current_filing_id}, "
            f"previous_filing_id={self.previous_filing_id}, status={self.status!r})>"
        )


class FilingSectionDiff(Base):
    """Normalized representation of section-level changes."""

    __tablename__ = "filing_section_diffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_diff_id: Mapped[int] = mapped_column(
        ForeignKey("filing_diffs.id"), nullable=False, index=True
    )
    current_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("filing_sections.id"), nullable=True, index=True
    )
    previous_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("filing_sections.id"), nullable=True, index=True
    )
    analysis_id: Mapped[int | None] = mapped_column(
        ForeignKey("filing_analyses.id"), nullable=True, index=True
    )
    section_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    section_title: Mapped[str] = mapped_column(String(255), nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    impact: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    filing_diff: Mapped[FilingDiff] = relationship("FilingDiff", back_populates="section_diffs")
    current_section: Mapped[FilingSection | None] = relationship(
        "FilingSection",
        foreign_keys=[current_section_id],
        back_populates="section_diffs",
    )
    previous_section: Mapped[FilingSection | None] = relationship(
        "FilingSection",
        foreign_keys=[previous_section_id],
        back_populates="previous_section_diffs",
    )
    analysis: Mapped[FilingAnalysis | None] = relationship(
        "FilingAnalysis", back_populates="section_diffs"
    )

    def __repr__(self) -> str:
        return (
            f"<FilingSectionDiff(filing_diff_id={self.filing_diff_id}, "
            f"ordinal={self.section_ordinal}, change_type={self.change_type!r})>"
        )
