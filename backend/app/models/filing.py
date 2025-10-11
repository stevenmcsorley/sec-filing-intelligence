"""Filing and related models for SEC documents."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base

if TYPE_CHECKING:
    from .company import Company


class FilingStatus(str, Enum):
    """Filing processing status."""

    PENDING = "pending"
    DOWNLOADED = "downloaded"
    PARSED = "parsed"
    ANALYZED = "analyzed"
    FAILED = "failed"


class BlobKind(str, Enum):
    """Type of filing blob storage."""

    RAW = "raw"  # Original HTML/PDF/TXT
    TEXT = "text"  # Cleaned text
    SECTIONS = "sections"  # Sectionized JSON
    INDEX = "index"  # Filing index page


class Filing(Base):
    """SEC filing metadata and processing status."""

    __tablename__ = "filings"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    cik: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(10), index=True)
    form_type: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    filed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    accession_number: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )
    source_urls: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array as text
    status: Mapped[str] = mapped_column(
        String(20), default=FilingStatus.PENDING.value, index=True, nullable=False
    )
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    company: Mapped[Company] = relationship("Company", back_populates="filings")
    blobs: Mapped[list[FilingBlob]] = relationship(
        "FilingBlob", back_populates="filing", cascade="all, delete-orphan"
    )
    sections: Mapped[list[FilingSection]] = relationship(
        "FilingSection", back_populates="filing", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Filing(accession={self.accession_number!r}, "
            f"form={self.form_type!r}, status={self.status!r})>"
        )


class FilingBlob(Base):
    """Storage location for filing content blobs (raw, text, sections)."""

    __tablename__ = "filing_blobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_id: Mapped[int] = mapped_column(ForeignKey("filings.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)  # s3://bucket/key or minio URL
    checksum: Mapped[str | None] = mapped_column(String(64), index=True)
    content_type: Mapped[str | None] = mapped_column(String(100))

    # Relationships
    filing: Mapped[Filing] = relationship("Filing", back_populates="blobs")

    def __repr__(self) -> str:
        return f"<FilingBlob(filing_id={self.filing_id}, kind={self.kind!r})>"


class FilingSection(Base):
    """Parsed section from a filing with text content and vector embedding."""

    __tablename__ = "filing_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_id: Mapped[int] = mapped_column(ForeignKey("filings.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)  # Section order
    content: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str | None] = mapped_column(String(64), index=True)  # SHA256 for dedup
    # text_vector: pgvector column (to be added with pgvector extension)

    # Relationships
    filing: Mapped[Filing] = relationship("Filing", back_populates="sections")

    def __repr__(self) -> str:
        return (
            f"<FilingSection(filing_id={self.filing_id}, "
            f"title={self.title!r}, ordinal={self.ordinal})>"
        )
