"""Async workers that consume chunk jobs and generate section summaries via Groq."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.groq.budget import (
    BudgetExceededError,
    GroqBudgetLimiter,
    TokenReservation,
    record_budget_deferral,
)
from app.models.analysis import AnalysisType, FilingAnalysis
from app.models.filing import Filing, FilingSection
from app.orchestration.planner import ChunkTask
from app.orchestration.queue import ChunkQueue, ChunkQueueMessage

from .client import ChatCompletionResult, ChatMessage, GroqChatClient
from .metrics import (
    SECTION_SUMMARY_COMPLETIONS_TOTAL,
    SECTION_SUMMARY_ERRORS_TOTAL,
    SECTION_SUMMARY_LATENCY_SECONDS,
    SECTION_SUMMARY_TOKENS_TOTAL,
)

LOGGER = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an equity research analyst creating concise summaries of SEC filings. "
    "Focus on material changes, risk disclosures, liquidity updates, covenants, and "
    "forward-looking statements. Return bullet points (max 4) in plain English with no "
    "headings. If the text is boilerplate with no notable changes, include a single "
    "bullet stating 'No material updates detected.'"
)


@dataclass(slots=True)
class SectionSummaryOptions:
    """Runtime configuration for section summarization jobs."""

    model: str
    temperature: float
    max_output_tokens: int
    max_retries: int
    backoff_seconds: float


class RetryableLLMError(Exception):
    """Raised when Groq errors should trigger a retry."""


class FatalLLMError(Exception):
    """Raised when Groq errors should acknowledge the job and move on."""


class SectionSummaryWorker:
    """Worker that consumes chunk tasks and persists Groq-generated summaries."""

    def __init__(
        self,
        *,
        name: str,
        queue: ChunkQueue,
        session_factory: async_sessionmaker[AsyncSession],
        client: GroqChatClient,
        options: SectionSummaryOptions,
        budget: GroqBudgetLimiter | None = None,
    ) -> None:
        self._name = name
        self._queue = queue
        self._session_factory = session_factory
        self._client = client
        self._options = options
        self._budget = budget

    async def run(self, stop_event: asyncio.Event) -> None:
        """Continuously consume chunk tasks until stopped."""
        while not stop_event.is_set():
            message = await self._queue.pop(timeout=5)
            if message is None:
                continue

            acknowledge = False
            try:
                acknowledge = await self._handle_message(message)
            except asyncio.CancelledError:  # pragma: no cover - cooperative cancellation
                raise
            except Exception:  # pragma: no cover - defensive logging
                LOGGER.exception(
                    "Section summarizer crashed",
                    extra={"worker": self._name, "job_id": message.job_id},
                )
                SECTION_SUMMARY_ERRORS_TOTAL.labels("unexpected").inc()

            if acknowledge:
                try:
                    await self._queue.ack(message)
                except Exception:  # pragma: no cover - defensive logging
                    LOGGER.exception(
                        "Failed to acknowledge section summary job",
                        extra={"worker": self._name, "job_id": message.job_id},
                    )

    async def _handle_message(self, message: ChunkQueueMessage) -> bool:
        task = message.task
        start_time = datetime.now(UTC)

        filing, section = await self._load_section(task.accession_number, task.section_ordinal)
        if filing is None or section is None:
            LOGGER.warning(
                "Section summarizer missing filing/section metadata",
                extra={
                    "worker": self._name,
                    "accession": task.accession_number,
                    "section": task.section_ordinal,
                },
            )
            SECTION_SUMMARY_ERRORS_TOTAL.labels("missing_section").inc()
            return True

        messages = self._build_messages(task, section.title)
        reservation: TokenReservation | None = None
        try:
            if self._budget is not None:
                reservation = await self._budget.reserve(self._estimate_budget_tokens(task))
        except BudgetExceededError:
            if self._budget is not None:
                record_budget_deferral(self._budget)
            LOGGER.warning(
                "Section summarizer budget exhausted; deferring job",
                extra={
                    "worker": self._name,
                    "job_id": message.job_id,
                    "accession": task.accession_number,
                },
            )
            await asyncio.sleep(self._cooldown_delay())
            return False

        try:
            result = await self._summarize_with_retry(messages)
        except RetryableLLMError:
            if reservation is not None:
                await reservation.release()
            LOGGER.warning(
                "Retryable Groq error; requeueing job",
                extra={
                    "worker": self._name,
                    "job_id": message.job_id,
                    "accession": task.accession_number,
                },
            )
            SECTION_SUMMARY_ERRORS_TOTAL.labels("groq_retryable").inc()
            return False
        except FatalLLMError:
            if reservation is not None:
                await reservation.release()
            LOGGER.error(
                "Fatal Groq error; acknowledging job",
                extra={
                    "worker": self._name,
                    "job_id": message.job_id,
                    "accession": task.accession_number,
                },
            )
            SECTION_SUMMARY_ERRORS_TOTAL.labels("groq_fatal").inc()
            return True

        await self._persist_analysis(
            job_id=message.job_id,
            filing_id=filing.id,
            section_id=section.id,
            chunk_index=task.chunk_index,
            summary=result.content,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            metadata={
                "section_title": section.title,
                "start_paragraph_index": task.start_paragraph_index,
                "end_paragraph_index": task.end_paragraph_index,
            },
        )

        elapsed = (datetime.now(UTC) - start_time).total_seconds()
        SECTION_SUMMARY_LATENCY_SECONDS.labels(result.model).observe(elapsed)
        SECTION_SUMMARY_COMPLETIONS_TOTAL.labels(result.model).inc()
        if result.prompt_tokens:
            SECTION_SUMMARY_TOKENS_TOTAL.labels("prompt").inc(result.prompt_tokens)
        if result.completion_tokens:
            SECTION_SUMMARY_TOKENS_TOTAL.labels("completion").inc(result.completion_tokens)
        if reservation is not None:
            await reservation.commit(self._resolve_total_tokens(result))
        return True

    async def _load_section(
        self, accession_number: str, section_ordinal: int
    ) -> tuple[Filing | None, FilingSection | None]:
        async with self._session_factory() as session:
            filing_stmt = select(Filing).where(Filing.accession_number == accession_number)
            filing = (await session.execute(filing_stmt)).scalar_one_or_none()
            if filing is None:
                return None, None
            section_stmt = (
                select(FilingSection)
                .where(
                    FilingSection.filing_id == filing.id,
                    FilingSection.ordinal == section_ordinal,
                )
                .limit(1)
            )
            section = (await session.execute(section_stmt)).scalar_one_or_none()
            return filing, section

    def _build_messages(self, task: ChunkTask, section_title: str) -> list[ChatMessage]:
        content = task.content.strip()
        if not content:
            content = "No content provided."
        user_prompt = (
            f"Filing accession: {task.accession_number}\n"
            f"Section title: {section_title}\n"
            f"Chunk index: {task.chunk_index}\n"
            f"Paragraph span: {task.start_paragraph_index}-{task.end_paragraph_index}\n\n"
            "Section text:\n"
            f"{content}"
        )
        return [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]

    def _estimate_budget_tokens(self, task: ChunkTask) -> int:
        prompt_estimate = max(task.estimated_tokens, len(task.content) // 4)
        return prompt_estimate + self._options.max_output_tokens

    async def _summarize_with_retry(self, messages: list[ChatMessage]) -> ChatCompletionResult:
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
                if status in {408, 429} or status >= 500:
                    attempt += 1
                    if attempt > self._options.max_retries:
                        raise RetryableLLMError from exc
                    await asyncio.sleep(self._options.backoff_seconds * attempt)
                    continue
                raise FatalLLMError from exc
            except httpx.HTTPError as exc:
                attempt += 1
                if attempt > self._options.max_retries:
                    raise RetryableLLMError from exc
                await asyncio.sleep(self._options.backoff_seconds * attempt)
            except RuntimeError as exc:
                raise FatalLLMError from exc

    def _resolve_total_tokens(self, result: ChatCompletionResult) -> int:
        total = result.total_tokens
        if total <= 0:
            total = result.prompt_tokens + result.completion_tokens
        if total <= 0:
            total = self._options.max_output_tokens
        return total

    def _cooldown_delay(self) -> float:
        if self._budget is None:
            return 1.0
        return max(float(self._budget.cooldown_seconds), 1.0)

    async def _persist_analysis(
        self,
        *,
        job_id: str,
        filing_id: int,
        section_id: int,
        chunk_index: int,
        summary: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        metadata: dict[str, int | str],
    ) -> None:
        payload = json.dumps(metadata, sort_keys=True)
        async with self._session_factory() as session:
            async with session.begin():
                stmt = select(FilingAnalysis).where(FilingAnalysis.job_id == job_id).limit(1)
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if existing is None:
                    analysis = FilingAnalysis(
                        job_id=job_id,
                        filing_id=filing_id,
                        section_id=section_id,
                        chunk_index=chunk_index,
                        analysis_type=AnalysisType.SECTION_CHUNK_SUMMARY.value,
                        model=model,
                        content=summary or "No material updates detected.",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        extra=payload,
                    )
                    session.add(analysis)
                else:
                    existing.section_id = section_id
                    existing.chunk_index = chunk_index
                    existing.model = model
                    existing.content = summary or "No material updates detected."
                    existing.prompt_tokens = prompt_tokens
                    existing.completion_tokens = completion_tokens
                    existing.total_tokens = total_tokens
                    existing.extra = payload
