"""Chunk planning utilities for Groq AI orchestration."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass


def _to_int(value: object, *, field: str) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"Expected int-compatible value for {field}, got {type(value)!r}")


@dataclass(slots=True)
class ChunkPlannerOptions:
    """Controls how filing sections are chunked for LLM jobs."""

    max_tokens_per_chunk: int = 800
    min_tokens_per_chunk: int = 200
    paragraph_overlap: int = 1


@dataclass(slots=True)
class PlannerSection:
    """Normalized section input for the chunk planner."""

    ordinal: int
    title: str
    content: str


@dataclass(slots=True)
class ChunkTask:
    """Chunk job payload submitted to the Groq job queue."""

    job_id: str
    accession_number: str
    section_ordinal: int
    section_title: str
    chunk_index: int
    start_paragraph_index: int
    end_paragraph_index: int
    content: str
    estimated_tokens: int

    def to_payload(self) -> dict[str, str | int]:
        return {
            "job_id": self.job_id,
            "accession_number": self.accession_number,
            "section_ordinal": self.section_ordinal,
            "section_title": self.section_title,
            "chunk_index": self.chunk_index,
            "start_paragraph_index": self.start_paragraph_index,
            "end_paragraph_index": self.end_paragraph_index,
            "content": self.content,
            "estimated_tokens": self.estimated_tokens,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> ChunkTask:
        return cls(
            job_id=str(payload["job_id"]),
            accession_number=str(payload["accession_number"]),
            section_ordinal=_to_int(payload["section_ordinal"], field="section_ordinal"),
            section_title=str(payload["section_title"]),
            chunk_index=_to_int(payload["chunk_index"], field="chunk_index"),
            start_paragraph_index=_to_int(
                payload["start_paragraph_index"], field="start_paragraph_index"
            ),
            end_paragraph_index=_to_int(
                payload["end_paragraph_index"], field="end_paragraph_index"
            ),
            content=str(payload["content"]),
            estimated_tokens=_to_int(payload["estimated_tokens"], field="estimated_tokens"),
        )

    def with_job_id(self, job_id: str) -> ChunkTask:
        return ChunkTask(
            job_id=job_id,
            accession_number=self.accession_number,
            section_ordinal=self.section_ordinal,
            section_title=self.section_title,
            chunk_index=self.chunk_index,
            start_paragraph_index=self.start_paragraph_index,
            end_paragraph_index=self.end_paragraph_index,
            content=self.content,
            estimated_tokens=self.estimated_tokens,
        )


class ChunkPlanner:
    """Split parsed sections into hierarchical chunks for Groq processing."""

    def __init__(self, options: ChunkPlannerOptions | None = None) -> None:
        self._options = options or ChunkPlannerOptions()

    def plan(self, accession_number: str, sections: Iterable[PlannerSection]) -> list[ChunkTask]:
        """Generate chunk jobs for the provided sections."""
        jobs: list[ChunkTask] = []
        for section in sections:
            paragraphs = self._split_paragraphs(section.content)
            if not paragraphs:
                continue

            index = 0
            chunk_index = 0
            while index < len(paragraphs):
                chunk_paragraphs: list[str] = []
                chunk_tokens = 0
                start_index = index
                cursor = index

                while cursor < len(paragraphs):
                    paragraph = paragraphs[cursor]
                    if not paragraph:
                        cursor += 1
                        continue

                    para_tokens = self._estimate_tokens(paragraph)
                    if (
                        chunk_paragraphs
                        and chunk_tokens + para_tokens > self._options.max_tokens_per_chunk
                    ):
                        break

                    chunk_paragraphs.append(paragraph)
                    chunk_tokens += para_tokens
                    cursor += 1

                    if chunk_tokens >= self._options.max_tokens_per_chunk:
                        break

                if not chunk_paragraphs:
                    paragraph = (
                        paragraphs[cursor] if cursor < len(paragraphs) else paragraphs[index]
                    )
                    paragraph = paragraph or ""
                    chunk_paragraphs.append(paragraph)
                    chunk_tokens = self._estimate_tokens(paragraph)
                    cursor = min(cursor + 1, len(paragraphs))

                while (
                    chunk_tokens < self._options.min_tokens_per_chunk and cursor < len(paragraphs)
                ):
                    paragraph = paragraphs[cursor]
                    if paragraph:
                        chunk_paragraphs.append(paragraph)
                        chunk_tokens += self._estimate_tokens(paragraph)
                    cursor += 1

                content = "\n\n".join(chunk_paragraphs).strip()
                if not content:
                    index = max(cursor, index + 1)
                    continue

                job_id = f"{accession_number}:{section.ordinal}:{chunk_index}"
                jobs.append(
                    ChunkTask(
                        job_id=job_id,
                        accession_number=accession_number,
                        section_ordinal=section.ordinal,
                        section_title=section.title,
                        chunk_index=chunk_index,
                        start_paragraph_index=start_index,
                        end_paragraph_index=max(cursor - 1, start_index),
                        content=content,
                        estimated_tokens=chunk_tokens,
                    )
                )
                chunk_index += 1

                if cursor >= len(paragraphs):
                    break

                overlap = max(0, self._options.paragraph_overlap)
                index = max(cursor - overlap, start_index + 1)

        return jobs

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        normalized = re.sub(r"\r\n", "\n", text)
        blocks = re.split(r"\n{2,}", normalized)
        return [block.strip() for block in blocks]

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        if not text:
            return 0
        words = len(text.split())
        return max(1, math.ceil(words * 1.3))
