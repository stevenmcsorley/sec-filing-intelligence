from __future__ import annotations

from pathlib import Path

from app.parsing.sectionizer import extract_sections, html_to_text

FIXTURES = Path(__file__).parent / "fixtures" / "parsing"


def test_html_to_text_extracts_content() -> None:
    html = (FIXTURES / "sample_html.html").read_text()
    text = html_to_text(html)
    assert "Business" in text


def test_extract_sections_from_text() -> None:
    text = (FIXTURES / "sample_text.txt").read_text()
    sections = extract_sections(text)
    titles = [section.title for section in sections]
    assert any("Item 1" in title for title in titles)
    assert any("Risk Factors" in title for title in titles)
    assert len(sections) == 3
