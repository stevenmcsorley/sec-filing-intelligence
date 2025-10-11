from __future__ import annotations

import pytest
from app.orchestration.planner import ChunkPlanner, ChunkPlannerOptions, PlannerSection


def _make_sections() -> list[PlannerSection]:
    content = (
        "Paragraph one about business outlook.\n\n"
        "Paragraph two with more detail and some additional sentences.\n\n"
        "Paragraph three contains risk discussion and implications for investors.\n\n"
        "Paragraph four summarizes the strategy going forward."
    )
    return [PlannerSection(ordinal=1, title="Management Discussion", content=content)]


def test_chunk_planner_generates_overlapping_chunks() -> None:
    planner = ChunkPlanner(
        ChunkPlannerOptions(
            max_tokens_per_chunk=30,
            min_tokens_per_chunk=10,
            paragraph_overlap=1,
        )
    )
    sections = _make_sections()
    jobs = planner.plan("0000000000-00-000001", sections)

    assert len(jobs) >= 2
    assert jobs[0].accession_number == "0000000000-00-000001"
    assert jobs[0].section_ordinal == 1
    assert jobs[0].estimated_tokens >= 10
    assert jobs[0].end_paragraph_index >= jobs[0].start_paragraph_index

    # Ensure overlap by paragraph index
    assert jobs[1].start_paragraph_index <= jobs[0].end_paragraph_index


@pytest.mark.parametrize(
    "overlap",
    [0, 2],
)
def test_chunk_planner_respects_paragraph_overlap(overlap: int) -> None:
    planner = ChunkPlanner(
        ChunkPlannerOptions(
            max_tokens_per_chunk=40,
            min_tokens_per_chunk=10,
            paragraph_overlap=overlap,
        )
    )
    jobs = planner.plan("0000000000-00-000002", _make_sections())
    assert jobs, "Expected at least one chunk job"
    last_end = -1
    for job in jobs:
        assert job.start_paragraph_index >= max(0, last_end - overlap)
        last_end = job.end_paragraph_index
