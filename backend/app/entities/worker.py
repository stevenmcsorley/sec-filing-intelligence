"""Entity extraction workers leveraging Groq LLMs."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

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
from app.models.entity import FilingEntity
from app.models.filing import Filing, FilingSection
from app.orchestration.planner import ChunkTask
from app.orchestration.queue import ChunkQueue, ChunkQueueMessage
from app.summarization.client import ChatCompletionResult, ChatMessage, GroqChatClient

from .metrics import (
    ENTITY_EXTRACTION_COMPLETIONS_TOTAL,
    ENTITY_EXTRACTION_ENTITIES_TOTAL,
    ENTITY_EXTRACTION_ERRORS_TOTAL,
    ENTITY_EXTRACTION_LATENCY_SECONDS,
    ENTITY_EXTRACTION_TOKENS_TOTAL,
)

LOGGER = logging.getLogger(__name__)

_ENTITY_TYPES = [
    "executive_change",
    "guidance_update",
    "litigation",
    "debt_covenant",
    "related_party_transaction",
    "risk_factor_change",
    "other",
]

_SYSTEM_PROMPT = (
    "You are an analyst extracting material events from SEC filings. "
    "Return ONLY a JSON array. Each element must include: "
    "`type` (one of "
    + ", ".join(f"'{t}'" for t in _ENTITY_TYPES)
    + "), `entity` (concise description), `confidence` (0-1 decimal), "
    "`evidence` (verbatim excerpt), and optional `metadata` object with structured details "
    "(e.g., {'action':'resigned','effective_date':'2024-01-15'}). "
    "If nothing material is present, respond with an empty array []. "
    "Never speculate beyond the provided text."
)


@dataclass(slots=True)
class EntityExtractionOptions:
    model: str
    temperature: float
    max_output_tokens: int
    max_retries: int
    backoff_seconds: float


class RetryableEntityError(Exception):
    """Raised when Groq errors should trigger a retry."""


class FatalEntityError(Exception):
    """Raised when Groq errors should acknowledge the job and move on."""


class EntityExtractionWorker:
    """Worker that extracts structured entities from chunked filings."""

    def __init__(
        self,
        *,
        name: str,
        queue: ChunkQueue,
        session_factory: async_sessionmaker[AsyncSession],
        client: GroqChatClient,
        options: EntityExtractionOptions,
        budget: GroqBudgetLimiter | None = None,
    ) -> None:
        self._name = name
        self._queue = queue
        self._session_factory = session_factory
        self._client = client
        self._options = options
        self._budget = budget

    async def run(self, stop_event: asyncio.Event) -> None:
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
                    "Entity extraction worker crashed",
                    extra={"worker": self._name, "job_id": message.job_id},
                )
                ENTITY_EXTRACTION_ERRORS_TOTAL.labels("unexpected").inc()

            if acknowledge:
                try:
                    await self._queue.ack(message)
                except Exception:  # pragma: no cover - defensive logging
                    LOGGER.exception(
                        "Failed to acknowledge entity extraction job",
                        extra={"worker": self._name, "job_id": message.job_id},
                    )

    async def _handle_message(self, message: ChunkQueueMessage) -> bool:
        task = message.task
        start = datetime.now(UTC)

        filing, section = await self._load_section(task.accession_number, task.section_ordinal)
        if filing is None or section is None:
            LOGGER.warning(
                "Entity extraction missing filing/section metadata",
                extra={
                    "worker": self._name,
                    "accession": task.accession_number,
                    "section": task.section_ordinal,
                },
            )
            ENTITY_EXTRACTION_ERRORS_TOTAL.labels("missing_section").inc()
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
                "Entity extraction budget exhausted; deferring job",
                extra={
                    "worker": self._name,
                    "job_id": message.job_id,
                    "accession": task.accession_number,
                },
            )
            await asyncio.sleep(self._cooldown_delay())
            return False

        try:
            result = await self._extract_with_retry(messages)
        except RetryableEntityError:
            if reservation is not None:
                await reservation.release()
            LOGGER.warning(
                "Retryable Groq error; requeueing entity job",
                extra={
                    "worker": self._name,
                    "job_id": message.job_id,
                    "accession": task.accession_number,
                },
            )
            ENTITY_EXTRACTION_ERRORS_TOTAL.labels("groq_retryable").inc()
            return False
        except FatalEntityError:
            if reservation is not None:
                await reservation.release()
            LOGGER.error(
                "Fatal Groq error; acknowledging entity job",
                extra={
                    "worker": self._name,
                    "job_id": message.job_id,
                    "accession": task.accession_number,
                },
            )
            ENTITY_EXTRACTION_ERRORS_TOTAL.labels("groq_fatal").inc()
            return True

        try:
            entities = self._parse_entities(result.content)
        except ValueError:
            LOGGER.error(
                "Failed to parse entity extraction response",
                extra={"worker": self._name, "job_id": message.job_id, "content": result.content},
            )
            ENTITY_EXTRACTION_ERRORS_TOTAL.labels("parse").inc()
            return True

        try:
            await self._persist_entities(
                job_id=message.job_id,
                filing_id=filing.id,
                section_id=section.id,
                entities=entities,
                model=result.model,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens,
                metadata={
                    "section_title": section.title,
                    "chunk_index": task.chunk_index,
                    "start_paragraph_index": task.start_paragraph_index,
                    "end_paragraph_index": task.end_paragraph_index,
                },
            )

            elapsed = (datetime.now(UTC) - start).total_seconds()
            ENTITY_EXTRACTION_LATENCY_SECONDS.labels(result.model).observe(elapsed)
            ENTITY_EXTRACTION_COMPLETIONS_TOTAL.labels(result.model).inc()
            if result.prompt_tokens:
                ENTITY_EXTRACTION_TOKENS_TOTAL.labels("prompt").inc(result.prompt_tokens)
            if result.completion_tokens:
                ENTITY_EXTRACTION_TOKENS_TOTAL.labels("completion").inc(result.completion_tokens)
            for entity in entities:
                ENTITY_EXTRACTION_ENTITIES_TOTAL.labels(entity["type"]).inc()
            if reservation is not None:
                await reservation.commit(self._resolve_total_tokens(result))
        except Exception:
            if reservation is not None:
                await reservation.release()
            raise
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
        content = task.content.strip() or "No content provided."
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

    async def _extract_with_retry(self, messages: list[ChatMessage]) -> ChatCompletionResult:
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
                        raise RetryableEntityError from exc
                    await asyncio.sleep(self._options.backoff_seconds * attempt)
                    continue
                raise FatalEntityError from exc
            except httpx.HTTPError as exc:
                attempt += 1
                if attempt > self._options.max_retries:
                    raise RetryableEntityError from exc
                await asyncio.sleep(self._options.backoff_seconds * attempt)
            except RuntimeError as exc:
                raise FatalEntityError from exc

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

    def _parse_entities(self, raw: str) -> list[dict[str, Any]]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Groq response was not valid JSON") from exc

        if isinstance(data, dict) and "entities" in data:
            data = data["entities"]
        if not isinstance(data, list):
            raise ValueError("Expected JSON array of entities")

        normalized: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            entity_type = str(item.get("type", "other")).strip().lower().replace(" ", "_")
            if entity_type not in _ENTITY_TYPES:
                entity_type = "other"

            label = str(item.get("entity") or item.get("label") or "").strip()
            if not label:
                continue

            evidence_source = item.get("evidence") or item.get("supporting_text") or ""
            evidence = str(evidence_source).strip() or None

            metadata_obj: dict[str, Any] = {}
            raw_metadata = item.get("metadata") or item.get("details") or item.get("extra")
            if isinstance(raw_metadata, dict):
                metadata_obj = raw_metadata

            confidence_raw = item.get("confidence")
            confidence_val: float | None = None
            if confidence_raw is not None:
                try:
                    confidence_val = float(confidence_raw)
                except (TypeError, ValueError):
                    confidence_val = None
                else:
                    if confidence_val < 0 or confidence_val > 1:
                        confidence_val = None

            normalized.append(
                {
                    "type": entity_type,
                    "label": label,
                    "confidence": confidence_val,
                    "evidence": evidence,
                    "metadata": metadata_obj,
                }
            )
        return normalized

    async def _persist_entities(
        self,
        *,
        job_id: str,
        filing_id: int,
        section_id: int,
        entities: list[dict[str, Any]],
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        metadata: dict[str, int | str],
    ) -> None:
        payload = json.dumps(entities, sort_keys=True)
        extra = json.dumps(metadata, sort_keys=True)
        async with self._session_factory() as session:
            async with session.begin():
                stmt = select(FilingAnalysis).where(FilingAnalysis.job_id == job_id).limit(1)
                analysis = (await session.execute(stmt)).scalar_one_or_none()
                if analysis is None:
                    analysis = FilingAnalysis(
                        job_id=job_id,
                        filing_id=filing_id,
                        section_id=section_id,
                        chunk_index=None,
                        analysis_type=AnalysisType.ENTITY_EXTRACTION.value,
                        model=model,
                        content=payload,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        extra=extra,
                    )
                    session.add(analysis)
                else:
                    analysis.model = model
                    analysis.content = payload
                    analysis.prompt_tokens = prompt_tokens
                    analysis.completion_tokens = completion_tokens
                    analysis.total_tokens = total_tokens
                    analysis.extra = extra
                    analysis.section_id = section_id
                    analysis.entities.clear()

                for entity in entities:
                    metadata_json = None
                    if entity["metadata"]:
                        metadata_json = json.dumps(entity["metadata"], sort_keys=True)
                    analysis.entities.append(
                        FilingEntity(
                            filing_id=filing_id,
                            section_id=section_id,
                            entity_type=entity["type"],
                            label=entity["label"],
                            confidence=entity["confidence"],
                            source_excerpt=entity["evidence"],
                            attributes=metadata_json,
                        )
                    )
