"""Filing-related API routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_token
from app.auth.models import TokenContext
from app.db import get_db_session
from app.models.diff import FilingDiff, FilingSectionDiff
from app.repositories import FilingRepository

router = APIRouter(prefix="/filings", tags=["filings"])


@router.get("/")
async def list_filings(
    token: Annotated[TokenContext, Depends(get_current_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    cik: Annotated[str | None, Query()] = None,
    ticker: Annotated[str | None, Query()] = None,
    form_type: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    filed_after: Annotated[datetime | None, Query()] = None,
    filed_before: Annotated[datetime | None, Query()] = None,
) -> dict[str, Any]:
    """List filings with optional filters and pagination."""
    # Token validated but not currently used for authorization
    # pending OPA integration

    repo = FilingRepository(db)
    filings = await repo.list_filings(
        limit=limit,
        offset=offset,
        cik=cik,
        ticker=ticker,
        form_type=form_type,
        status=status,
        filed_after=filed_after,
        filed_before=filed_before,
    )

    # Skip analysis loading for list view to improve performance

    # Convert to API response format
    filing_list = []
    for filing in filings:
        # For Form 4, 144, and Schedule 13D/A filings, try to extract
        # issuer company information from analysis
        company_name = filing.company.name if filing.company else None
        extracted_ticker = filing.company.ticker if filing.company else filing.ticker
        
        if filing.form_type in ['4', '144', 'SCHEDULE 13D/A', '3']:
            # Skip expensive SEC API lookups on every request - rely on pre-processed data
            # The company information should already be correct from our reprocessing scripts
            pass
        
        filing_list.append({
            "id": filing.id,
            "cik": filing.cik,
            "ticker": extracted_ticker,
            "company_name": company_name,
            "form_type": filing.form_type,
            "filed_at": filing.filed_at,
            "accession_number": filing.accession_number,
            "status": filing.status,
            "downloaded_at": filing.downloaded_at,
            "section_count": len(filing.sections),
            "blob_count": len(filing.blobs),
            "analysis": None,  # Skip analysis for list view to improve performance
        })

    # Get total count for pagination
    total_count = await repo.count_filings(
        cik=cik,
        ticker=ticker,
        form_type=form_type,
        status=status,
        filed_after=filed_after,
        filed_before=filed_before,
    )

    return {
        "filings": filing_list,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{filing_id}")
async def get_filing(
    token: Annotated[TokenContext, Depends(get_current_token)],
    filing_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Get detailed information about a specific filing."""
    # Token validated but not currently used for authorization
    # pending OPA integration

    repo = FilingRepository(db)
    filing = await repo.get_filing_by_id(filing_id)

    if filing is None:
        raise HTTPException(status_code=404, detail="Filing not found")

    # Get blob information
    blobs = []
    for blob in filing.blobs:
        blobs.append({
            "id": blob.id,
            "kind": blob.kind,
            "location": blob.location,
            "checksum": blob.checksum,
            "content_type": blob.content_type,
        })

    # Get section information
    sections = []
    for section in filing.sections:
        sections.append({
            "id": section.id,
            "title": section.title,
            "ordinal": section.ordinal,
            "content_length": len(section.content),
            "text_hash": section.text_hash,
        })

    # Get analysis for this filing (latest one) - currently unused
    # but kept for future analysis features
    
    # For Form 4, 144, and Schedule 13D/A filings, try to extract
    # issuer company information from analysis
    company_name = filing.company.name if filing.company else None
    extracted_ticker = filing.company.ticker if filing.company else filing.ticker
    
    print(f"API: Filing {filing.id}, company loaded: "
          f"{filing.company is not None}, ticker: {extracted_ticker}")

    return {
        "id": filing.id,
        "cik": filing.cik,
        "ticker": extracted_ticker,
        "company_name": company_name,
        "form_type": filing.form_type,
        "filed_at": filing.filed_at,
        "accession_number": filing.accession_number,
        "source_urls": filing.source_urls,
        "status": filing.status,
        "downloaded_at": filing.downloaded_at,
        "blobs": blobs,
        "sections": sections,
        "section_count": len(sections),
        "blob_count": len(blobs),
    }


@router.get("/{filing_id}/sections")
async def get_filing_sections(
    token: Annotated[TokenContext, Depends(get_current_token)],
    filing_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    """Get all sections for a specific filing."""
    # Token validated but not currently used for authorization
    # pending OPA integration

    repo = FilingRepository(db)
    filing = await repo.get_filing_by_id(filing_id)

    if filing is None:
        raise HTTPException(status_code=404, detail="Filing not found")

    sections = []
    for section in sorted(filing.sections, key=lambda s: s.ordinal):
        sections.append({
            "id": section.id,
            "title": section.title,
            "ordinal": section.ordinal,
            "content": section.content,
            "text_hash": section.text_hash,
        })

    return sections


@router.get("/{filing_id}/content")
async def get_filing_content(
    token: Annotated[TokenContext, Depends(get_current_token)],
    filing_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    kind: Annotated[str, Query(pattern="^(raw|text|sections)$")] = "text",
) -> dict[str, Any]:
    """Get filing content by kind (raw, text, or sections)."""
    # Token validated but not currently used for authorization
    # pending OPA integration

    repo = FilingRepository(db)
    filing = await repo.get_filing_by_id(filing_id)

    if filing is None:
        raise HTTPException(status_code=404, detail="Filing not found")

    # Find the blob of the requested kind
    blob = next((b for b in filing.blobs if b.kind == kind), None)
    if blob is None:
        raise HTTPException(
            status_code=404,
            detail=f"No {kind} content found for filing {filing_id}"
        )

    # For now, return blob metadata. In a real implementation,
    # you'd fetch the actual content from MinIO and return it
    return {
        "filing_id": filing.id,
        "kind": blob.kind,
        "location": blob.location,
        "checksum": blob.checksum,
        "content_type": blob.content_type,
        "accession_number": filing.accession_number,
    }


@router.get("/{filing_id}/diff")
async def get_filing_diff(
    token: Annotated[TokenContext, Depends(get_current_token)],
    filing_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    # Token validated but not currently used for authorization
    # pending OPA integration
    diff_stmt = (
        select(FilingDiff)
        .where(FilingDiff.current_filing_id == filing_id)
        .options(
            selectinload(FilingDiff.section_diffs).selectinload(FilingSectionDiff.current_section),
            selectinload(FilingDiff.section_diffs).selectinload(FilingSectionDiff.previous_section),
        )
    )
    diff = (await db.execute(diff_stmt)).scalar_one_or_none()
    if diff is None:
        raise HTTPException(status_code=404, detail="Diff not found")

    sections: dict[int, dict[str, Any]] = {}
    for entry in diff.section_diffs:
        bucket = sections.setdefault(
            entry.section_ordinal,
            {
                "section_ordinal": entry.section_ordinal,
                "section_title": entry.section_title,
                "current_section_id": entry.current_section_id,
                "previous_section_id": entry.previous_section_id,
                "analysis_id": entry.analysis_id,
                "changes": [],
            },
        )
        bucket["changes"].append(
            {
                "change_type": entry.change_type,
                "summary": entry.summary,
                "impact": entry.impact,
                "confidence": entry.confidence,
                "evidence": entry.evidence,
            }
        )

    section_list = sorted(sections.values(), key=lambda item: item["section_ordinal"])

    return {
        "filing_id": diff.current_filing_id,
        "previous_filing_id": diff.previous_filing_id,
        "status": diff.status,
        "expected_sections": diff.expected_sections,
        "processed_sections": diff.processed_sections,
        "last_error": diff.last_error,
        "updated_at": diff.updated_at,
        "sections": section_list,
    }
