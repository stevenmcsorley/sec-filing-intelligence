"""Filing-related API routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_token
from app.auth.models import TokenContext
from app.db import get_db_session
from app.models.diff import FilingDiff, FilingSectionDiff

router = APIRouter(prefix="/filings", tags=["filings"])


@router.get("/{filing_id}/diff")
async def get_filing_diff(
    filing_id: int,
    token: Annotated[TokenContext, Depends(get_current_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    del token  # Token currently unused pending OPA integration.
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
