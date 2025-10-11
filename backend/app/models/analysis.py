"""Analysis and summarization artifacts for filings."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base

if TYPE_CHECKING:  # pragma: no cover - typing aid only
    from .diff import FilingSectionDiff
    from .entity import FilingEntity
    from .filing import Filing, FilingSection


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AnalysisType(str, Enum):
    """Kinds of analyses generated for filings."""

    SECTION_CHUNK_SUMMARY = "section_chunk_summary"
    SECTION_SUMMARY = "section_summary"
    FILING_BRIEF = "filing_brief"
    SECTION_DIFF = "section_diff"
    ENTITY_EXTRACTION = "entity_extraction"


class FilingAnalysis(Base):
    """LLM-generated analysis artifact tied to a filing (and optionally a section)."""

    __tablename__ = "filing_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    filing_id: Mapped[int] = mapped_column(ForeignKey("filings.id"), nullable=False, index=True)
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("filing_sections.id"), nullable=True, index=True
    )
    chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analysis_type: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    filing: Mapped[Filing] = relationship("Filing", back_populates="analyses")
    section: Mapped[FilingSection | None] = relationship(
        "FilingSection", back_populates="analyses"
    )
    entities: Mapped[list[FilingEntity]] = relationship(
        "FilingEntity", back_populates="analysis", cascade="all, delete-orphan"
    )
    section_diffs: Mapped[list[FilingSectionDiff]] = relationship(
        "FilingSectionDiff", back_populates="analysis", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<FilingAnalysis(job_id={self.job_id!r}, type={self.analysis_type!r}, "
            f"section_id={self.section_id}, model={self.model!r})>"
        )
