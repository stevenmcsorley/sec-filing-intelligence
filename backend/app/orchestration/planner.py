"""Chunk planning utilities for Groq AI orchestration with rule-based pre-analysis."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.analysis.rule_based import PreAnalysisResult, RuleBasedAnalyzer
from app.models.filing import Filing


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
class Chunk:
    """Represents a chunk of text with metadata."""
    
    start_index: int
    end_index: int
    content: str
    estimated_tokens: int


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
    """Plans chunk jobs for Groq AI orchestration."""

    def __init__(self, options: ChunkPlannerOptions | None = None) -> None:
        self.options = options or ChunkPlannerOptions()

    def plan(self, accession_number: str, sections: Iterable[PlannerSection]) -> list[ChunkTask]:
        """Generate chunk jobs for the given sections."""
        tasks = []
        job_id = f"{accession_number}-{int(__import__('time').time())}"

        for section in sections:
            chunks = self._chunk_section(section)
            for i, chunk in enumerate(chunks):
                task = ChunkTask(
                    job_id=job_id,
                    accession_number=accession_number,
                    section_ordinal=section.ordinal,
                    section_title=section.title,
                    chunk_index=i,
                    start_paragraph_index=chunk.start_index,
                    end_paragraph_index=chunk.end_index,
                    content=chunk.content,
                    estimated_tokens=chunk.estimated_tokens,
                )
                tasks.append(task)

        return tasks

    def _chunk_section(self, section: PlannerSection) -> list[Chunk]:
        """Split a section into chunks."""
        paragraphs = self._split_paragraphs(section.content)
        chunks: list[Chunk] = []
        current_chunk: list[str] = []
        current_tokens = 0

        for paragraph in paragraphs:
            paragraph_tokens = self._estimate_tokens(paragraph)
            
            # If adding this paragraph would exceed max tokens, start a new chunk
            max_tokens = self.options.max_tokens_per_chunk
            if current_tokens + paragraph_tokens > max_tokens and current_chunk:
                chunk_content = "\n\n".join(current_chunk)
                chunk_tokens = self._estimate_tokens(chunk_content)
                
                if chunk_tokens >= self.options.min_tokens_per_chunk:
                    chunks.append(Chunk(
                        start_index=len(chunks) * self.options.paragraph_overlap,
                        end_index=len(chunks) * self.options.paragraph_overlap + len(current_chunk),
                        content=chunk_content,
                        estimated_tokens=chunk_tokens,
                    ))
                
                current_chunk = [paragraph]
                current_tokens = paragraph_tokens
            else:
                current_chunk.append(paragraph)
                current_tokens += paragraph_tokens

        # Add the last chunk if it has content
        if current_chunk:
            chunk_content = "\n\n".join(current_chunk)
            chunk_tokens = self._estimate_tokens(chunk_content)
            
            if chunk_tokens >= self.options.min_tokens_per_chunk:
                chunks.append(Chunk(
                    start_index=len(chunks) * self.options.paragraph_overlap,
                    end_index=len(chunks) * self.options.paragraph_overlap + len(current_chunk),
                    content=chunk_content,
                    estimated_tokens=chunk_tokens,
                ))

        return chunks

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


@dataclass(slots=True)
class EnhancedChunkTask:
    """Enhanced chunk task with rule-based analysis results."""
    
    # Base ChunkTask fields
    job_id: str
    accession_number: str
    section_ordinal: int
    section_title: str
    chunk_index: int
    start_paragraph_index: int
    end_paragraph_index: int
    content: str
    estimated_tokens: int
    
    # Enhanced fields
    pre_analysis: PreAnalysisResult | None = None
    should_skip_groq: bool = False
    groq_prompt_focus: str | None = None

    def to_payload(self) -> dict[str, str | int | bool | None]:
        base_payload: dict[str, str | int | bool | None] = {
            "job_id": self.job_id,
            "accession_number": self.accession_number,
            "section_ordinal": self.section_ordinal,
            "section_title": self.section_title,
            "chunk_index": self.chunk_index,
            "start_paragraph_index": self.start_paragraph_index,
            "end_paragraph_index": self.end_paragraph_index,
            "content": self.content,
            "estimated_tokens": self.estimated_tokens,
            "should_skip_groq": self.should_skip_groq,
            "groq_prompt_focus": self.groq_prompt_focus,
            "pre_analysis_priority": (
                self.pre_analysis.priority.value if self.pre_analysis else None
            ),
            "pre_analysis_category": (
                self.pre_analysis.category.value if self.pre_analysis else None
            ),
            "pre_analysis_confidence": (
                str(self.pre_analysis.confidence) if self.pre_analysis else None
            ),
        }
        return base_payload

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> EnhancedChunkTask:
        base_task = ChunkTask.from_payload(payload)
        return cls(
            job_id=base_task.job_id,
            accession_number=base_task.accession_number,
            section_ordinal=base_task.section_ordinal,
            section_title=base_task.section_title,
            chunk_index=base_task.chunk_index,
            start_paragraph_index=base_task.start_paragraph_index,
            end_paragraph_index=base_task.end_paragraph_index,
            content=base_task.content,
            estimated_tokens=base_task.estimated_tokens,
            should_skip_groq=bool(payload.get("should_skip_groq", False)),
            groq_prompt_focus=(
                str(payload.get("groq_prompt_focus")) 
                if payload.get("groq_prompt_focus") else None
            ),
        )

    def with_job_id(self, job_id: str) -> EnhancedChunkTask:
        return EnhancedChunkTask(
            job_id=job_id,
            accession_number=self.accession_number,
            section_ordinal=self.section_ordinal,
            section_title=self.section_title,
            chunk_index=self.chunk_index,
            start_paragraph_index=self.start_paragraph_index,
            end_paragraph_index=self.end_paragraph_index,
            content=self.content,
            estimated_tokens=self.estimated_tokens,
            pre_analysis=self.pre_analysis,
            should_skip_groq=self.should_skip_groq,
            groq_prompt_focus=self.groq_prompt_focus,
        )


class EnhancedChunkPlanner(ChunkPlanner):
    """Enhanced chunk planner with rule-based pre-analysis."""

    def __init__(self, options: ChunkPlannerOptions | None = None) -> None:
        super().__init__(options)
        self._analyzer = RuleBasedAnalyzer()

    async def plan_with_analysis(
        self, 
        accession_number: str, 
        sections: Iterable[PlannerSection],
        filing: Filing,  # Filing object for analysis
        filing_sections: list  # List of FilingSection objects for analysis
    ) -> list[EnhancedChunkTask]:
        """Generate enhanced chunk jobs with rule-based pre-analysis."""
        
        # Perform rule-based analysis on the filing
        pre_analysis = await self._analyzer.analyze_filing(filing, filing_sections)
        
        # Generate base chunk tasks
        base_tasks = self.plan(accession_number, sections)
        
        # Convert to enhanced tasks with analysis results
        enhanced_tasks = []
        for task in base_tasks:
            enhanced_task = EnhancedChunkTask(
                job_id=task.job_id,
                accession_number=task.accession_number,
                section_ordinal=task.section_ordinal,
                section_title=task.section_title,
                chunk_index=task.chunk_index,
                start_paragraph_index=task.start_paragraph_index,
                end_paragraph_index=task.end_paragraph_index,
                content=task.content,
                estimated_tokens=task.estimated_tokens,
                pre_analysis=pre_analysis,
                should_skip_groq=not pre_analysis.should_use_groq,
                groq_prompt_focus=pre_analysis.groq_prompt_focus,
            )
            enhanced_tasks.append(enhanced_task)
        
        return enhanced_tasks
