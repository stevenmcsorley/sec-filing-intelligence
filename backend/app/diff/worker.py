"""Diff workers that compare sequential filings and persist highlights."""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.models.analysis import AnalysisType, FilingAnalysis
from app.models.diff import DiffStatus, FilingDiff, FilingSectionDiff
from app.models.filing import Filing, FilingSection
from app.summarization.client import ChatCompletionResult, ChatMessage, GroqChatClient

from .metrics import (
    DIFF_CHANGES_TOTAL,
    DIFF_COMPLETIONS_TOTAL,
    DIFF_ERRORS_TOTAL,
    DIFF_LATENCY_SECONDS,
    DIFF_TOKENS_TOTAL,
)
from .queue import DiffQueue, DiffQueueMessage, DiffTask

LOGGER = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You compare two versions of the same SEC filing section. "
    "Given the unified diff or context provided, respond ONLY with a JSON array. "
    "Each element must include: change_type (addition|removal|update|rewording), "
    "summary (<=160 characters), impact (high|medium|low), confidence (0-1 decimal), "
    "and evidence (verbatim excerpt supporting the change). "
    "If no material changes are present, respond with an empty array []."
)


@dataclass(slots=True)
class DiffOptions:
    """Runtime configuration for diff jobs."""

    model: str
    temperature: float
    max_output_tokens: int
    max_retries: int
    backoff_seconds: float


class RetryableDiffError(Exception):
    """Raised when Groq errors should trigger a retry."""


class FatalDiffError(Exception):
    """Raised when Groq errors should acknowledge the job."""


class DiffWorker:
    """Worker that generates diff summaries between current and prior filings."""

    def __init__(
        self,
        *,
        name: str,
        queue: DiffQueue,
        session_factory: async_sessionmaker[AsyncSession],
        client: GroqChatClient,
        options: DiffOptions,
    ) -> None:
        self._name = name
        self._queue = queue
        self._session_factory = session_factory
        self._client = client
        self._options = options

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            message = await self._queue.pop(timeout=5)
            if message is None:
                continue

            acknowledge = False
            try:
                acknowledge = await self._handle_message(message)
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - defensive logging
                LOGGER.exception(
                    "Diff worker crashed",
                    extra={"worker": self._name, "job_id": message.job_id},
                )
                DIFF_ERRORS_TOTAL.labels("unexpected").inc()

            if acknowledge:
                try:
                    await self._queue.ack(message)
                except Exception:  # pragma: no cover - defensive logging
                    LOGGER.exception(
                        "Failed to acknowledge diff job",
                        extra={"worker": self._name, "job_id": message.job_id},
                    )

    async def _handle_message(self, message: DiffQueueMessage) -> bool:
        task = message.task
        start = datetime.now(UTC)

        metadata = await self._load_metadata(task)
        if metadata is None:
            DIFF_ERRORS_TOTAL.labels("metadata").inc()
            return True

        diff_record, current_section, previous_section, current_filing, previous_filing = metadata

        current_text = current_section.content if current_section is not None else ""
        previous_text = previous_section.content if previous_section is not None else ""

        if current_section is not None and previous_section is not None:
            if current_text.strip() == previous_text.strip():
                await self._finalize_noop(task.diff_id)
                DIFF_LATENCY_SECONDS.labels("noop").observe(
                    (datetime.now(UTC) - start).total_seconds()
                )
                return True

        diff_snippet = _build_diff_snippet(
            previous_text if previous_section is not None else None,
            current_text if current_section is not None else None,
        )

        changes: list[dict[str, Any]] = []
        analysis_result: ChatCompletionResult | None = None

        if diff_snippet.strip():
            messages = self._build_messages(
                task=task,
                current_filing=current_filing,
                previous_filing=previous_filing,
                diff_snippet=diff_snippet,
            )
            try:
                analysis_result = await self._diff_with_retry(messages)
            except RetryableDiffError:
                DIFF_ERRORS_TOTAL.labels("groq_retryable").inc()
                return False
            except FatalDiffError as exc:
                DIFF_ERRORS_TOTAL.labels("groq_fatal").inc()
                await self._mark_failed(task.diff_id, str(exc))
                return True

            try:
                changes = _parse_changes(analysis_result.content)
            except ValueError as exc:
                DIFF_ERRORS_TOTAL.labels("parse").inc()
                await self._mark_failed(task.diff_id, str(exc))
                return True
        else:
            changes = []

        if not changes:
            if previous_section is None and current_section is not None:
                changes = [
                    {
                        "change_type": "addition",
                        "summary": "New section added in the latest filing.",
                        "impact": "medium",
                        "confidence": 1.0,
                        "evidence": current_text[:280],
                    }
                ]
            elif current_section is None and previous_section is not None:
                changes = [
                    {
                        "change_type": "removal",
                        "summary": "Section removed compared to the previous filing.",
                        "impact": "medium",
                        "confidence": 1.0,
                        "evidence": previous_text[:280],
                    }
                ]

        await self._persist_results(
            task=task,
            current_section=current_section,
            previous_section=previous_section,
            changes=changes,
            analysis_result=analysis_result,
            diff_snippet=diff_snippet,
        )

        elapsed = (datetime.now(UTC) - start).total_seconds()
        model_label = analysis_result.model if analysis_result is not None else "noop"
        DIFF_LATENCY_SECONDS.labels(model_label).observe(elapsed)
        DIFF_COMPLETIONS_TOTAL.labels(model_label).inc()
        if analysis_result is not None:
            if analysis_result.prompt_tokens:
                DIFF_TOKENS_TOTAL.labels("prompt").inc(analysis_result.prompt_tokens)
            if analysis_result.completion_tokens:
                DIFF_TOKENS_TOTAL.labels("completion").inc(analysis_result.completion_tokens)
        for change in changes:
            DIFF_CHANGES_TOTAL.labels(change.get("change_type", "unknown")).inc()
        return True

    async def _load_metadata(
        self, task: DiffTask
    ) -> tuple[FilingDiff, FilingSection | None, FilingSection | None, Filing, Filing] | None:
        async with self._session_factory() as session:
            diff_stmt = (
                select(FilingDiff)
                .where(FilingDiff.id == task.diff_id)
                .options(
                    selectinload(FilingDiff.current_filing),
                    selectinload(FilingDiff.previous_filing),
                )
            )
            diff_record = (await session.execute(diff_stmt)).scalar_one_or_none()
            if diff_record is None:
                return None

            current_filing = diff_record.current_filing
            previous_filing = diff_record.previous_filing
            if current_filing is None or previous_filing is None:
                return None

            current_section: FilingSection | None = None
            previous_section: FilingSection | None = None

            if task.current_section_id is not None:
                current_section = (
                    await session.execute(
                        select(FilingSection).where(FilingSection.id == task.current_section_id)
                    )
                ).scalar_one_or_none()

            if task.previous_section_id is not None:
                previous_section = (
                    await session.execute(
                        select(FilingSection).where(FilingSection.id == task.previous_section_id)
                    )
                ).scalar_one_or_none()

            return diff_record, current_section, previous_section, current_filing, previous_filing

    async def _diff_with_retry(self, messages: list[ChatMessage]) -> ChatCompletionResult:
        attempt = 0
        while True:
            try:
                return await self._client.chat_completion(
                    model=self._options.model,
                    messages=messages,
                    max_tokens=self._options.max_output_tokens,
                    temperature=self._options.temperature,
                )
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in (429, 500, 502, 503, 504):
                    attempt += 1
                    if attempt > self._options.max_retries:
                        raise FatalDiffError(f"Exceeded retries: {exc}") from exc
                    await asyncio.sleep(self._options.backoff_seconds * attempt)
                    continue
                raise FatalDiffError(f"Groq request failed: {exc}") from exc
            except httpx.RequestError as exc:
                attempt += 1
                if attempt > self._options.max_retries:
                    raise FatalDiffError(f"Groq request error: {exc}") from exc
                await asyncio.sleep(self._options.backoff_seconds * attempt)
            except Exception as exc:  # pragma: no cover - defensive
                raise FatalDiffError(f"Unexpected Groq error: {exc}") from exc

    async def _persist_results(
        self,
        *,
        task: DiffTask,
        current_section: FilingSection | None,
        previous_section: FilingSection | None,
        changes: list[dict[str, Any]],
        analysis_result: ChatCompletionResult | None,
        diff_snippet: str,
    ) -> None:
        normalized_changes = [_normalize_change(change) for change in changes]

        metadata_json = json.dumps({"diff_snippet": diff_snippet}) if diff_snippet else None

        async with self._session_factory() as session:
            async with session.begin():
                locked_diff = (
                    await session.execute(
                        select(FilingDiff)
                        .where(FilingDiff.id == task.diff_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if locked_diff is None:
                    return

                await session.execute(
                    delete(FilingSectionDiff).where(
                        FilingSectionDiff.filing_diff_id == task.diff_id,
                        FilingSectionDiff.section_ordinal == task.section_ordinal,
                    )
                )

                existing_analysis = (
                    await session.execute(
                        select(FilingAnalysis)
                        .where(FilingAnalysis.job_id == task.job_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()

                analysis: FilingAnalysis | None = None
                if analysis_result is not None:
                    if existing_analysis is None:
                        analysis = FilingAnalysis(
                            job_id=task.job_id,
                            filing_id=locked_diff.current_filing_id,
                            section_id=current_section.id if current_section is not None else None,
                            chunk_index=None,
                            analysis_type=AnalysisType.SECTION_DIFF.value,
                            model=analysis_result.model,
                            content=analysis_result.content,
                            prompt_tokens=analysis_result.prompt_tokens,
                            completion_tokens=analysis_result.completion_tokens,
                            total_tokens=analysis_result.total_tokens,
                            extra=metadata_json,
                        )
                        session.add(analysis)
                    else:
                        analysis = existing_analysis
                        analysis.filing_id = locked_diff.current_filing_id
                        analysis.section_id = (
                            current_section.id if current_section is not None else None
                        )
                        analysis.chunk_index = None
                        analysis.analysis_type = AnalysisType.SECTION_DIFF.value
                        analysis.model = analysis_result.model
                        analysis.content = analysis_result.content
                        analysis.prompt_tokens = analysis_result.prompt_tokens
                        analysis.completion_tokens = analysis_result.completion_tokens
                        analysis.total_tokens = analysis_result.total_tokens
                        analysis.extra = metadata_json
                    await session.flush()
                elif existing_analysis is not None:
                    await session.delete(existing_analysis)
                    analysis = None

                for change in normalized_changes:
                    session.add(
                        FilingSectionDiff(
                            filing_diff_id=locked_diff.id,
                            current_section_id=current_section.id
                            if current_section is not None
                            else None,
                            previous_section_id=previous_section.id
                            if previous_section is not None
                            else None,
                            analysis_id=analysis.id if analysis is not None else None,
                            section_ordinal=task.section_ordinal,
                            section_title=task.section_title,
                            change_type=change["change_type"],
                            summary=change["summary"],
                            impact=change["impact"],
                            confidence=change.get("confidence"),
                            evidence=change.get("evidence"),
                        metadata_json=metadata_json,
                        )
                    )

                locked_diff.last_error = None
                if locked_diff.status in (
                    DiffStatus.PENDING.value,
                    DiffStatus.SKIPPED.value,
                ):
                    locked_diff.status = DiffStatus.PROCESSING.value
                locked_diff.processed_sections += 1
                locked_diff.updated_at = datetime.now(UTC)
                if locked_diff.processed_sections >= locked_diff.expected_sections:
                    if locked_diff.status != DiffStatus.FAILED.value:
                        locked_diff.status = DiffStatus.COMPLETED.value

    async def _mark_failed(self, diff_id: int, message: str) -> None:
        truncated = message[:2000]
        async with self._session_factory() as session:
            async with session.begin():
                diff_record = (
                    await session.execute(
                        select(FilingDiff)
                        .where(FilingDiff.id == diff_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if diff_record is None:
                    return
                diff_record.status = DiffStatus.FAILED.value
                diff_record.last_error = truncated
                diff_record.processed_sections = diff_record.expected_sections
                diff_record.updated_at = datetime.now(UTC)

    async def _finalize_noop(self, diff_id: int) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                locked_diff = (
                    await session.execute(
                        select(FilingDiff)
                        .where(FilingDiff.id == diff_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if locked_diff is None:
                    return
                if locked_diff.status in (
                    DiffStatus.PENDING.value,
                    DiffStatus.SKIPPED.value,
                ):
                    locked_diff.status = DiffStatus.PROCESSING.value
                locked_diff.processed_sections += 1
                locked_diff.updated_at = datetime.now(UTC)
                if locked_diff.processed_sections >= locked_diff.expected_sections:
                    if locked_diff.status != DiffStatus.FAILED.value:
                        locked_diff.status = DiffStatus.COMPLETED.value

    def _build_messages(
        self,
        *,
        task: DiffTask,
        current_filing: Filing,
        previous_filing: Filing,
        diff_snippet: str,
    ) -> list[ChatMessage]:
        header = (
            f"Current filing accession: {current_filing.accession_number}\n"
            f"Previous filing accession: {previous_filing.accession_number}\n"
            f"Section ordinal: {task.section_ordinal}\n"
            f"Section title: {task.section_title}\n"
        )
        user_content = header + "\nUnified diff:\n" + diff_snippet
        return [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content),
        ]


def _build_diff_snippet(
    previous_text: str | None,
    current_text: str | None,
    *,
    max_chars: int = 8000,
) -> str:
    prev_lines = (previous_text or "").splitlines()
    curr_lines = (current_text or "").splitlines()
    if not prev_lines and not curr_lines:
        return ""
    diff_lines = list(
        difflib.unified_diff(prev_lines, curr_lines, fromfile="previous", tofile="current", n=3)
    )
    snippet = "\n".join(diff_lines)
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars] + "\n..."
    return snippet


def _parse_changes(content: str) -> list[dict[str, Any]]:
    data = json.loads(content)
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError("Diff response must be a JSON array")
    changes: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        changes.append(entry)
    return changes


def _normalize_change(change: dict[str, Any]) -> dict[str, Any]:
    summary = str(change.get("summary") or "").strip()
    impact = str(change.get("impact") or "medium").lower()
    if impact not in {"high", "medium", "low"}:
        impact = "medium"
    change_type = str(change.get("change_type") or "update").lower()
    if change_type not in {"addition", "removal", "update", "rewording"}:
        change_type = "update"
    confidence_value = change.get("confidence")
    try:
        confidence = float(confidence_value) if confidence_value is not None else None
    except (TypeError, ValueError):
        confidence = None
    evidence = str(change.get("evidence") or "").strip()
    if len(summary) > 160:
        summary = summary[:157] + "..."
    return {
        "change_type": change_type,
        "summary": summary or "Change detected.",
        "impact": impact,
        "confidence": confidence,
        "evidence": evidence,
    }
