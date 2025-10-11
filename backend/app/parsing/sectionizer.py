"""Utilities for segmenting filings into sections."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass(slots=True)
class Section:
    title: str
    content: str


_ITEM_HEADING_RE = re.compile(r"^\s*(Item\s+[0-9A-Za-z\.]+\s*[A-Za-z ]*)", re.IGNORECASE)
_UPPER_HEADING_RE = re.compile(r"^\s*([A-Z][A-Z0-9 &/,\-]{5,})\s*$")


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    return _normalize_whitespace(text)


def _normalize_whitespace(text: str) -> str:
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_sections(text: str) -> list[Section]:
    text = _normalize_whitespace(text)
    lines = text.split("\n")
    indices: list[tuple[str, int]] = []
    for idx, line in enumerate(lines):
        headline = _ITEM_HEADING_RE.match(line)
        if headline:
            indices.append((headline.group(1).strip(), idx))
            continue
        upper = _UPPER_HEADING_RE.match(line)
        if upper:
            indices.append((upper.group(1).strip().title(), idx))

    if not indices:
        return [Section(title="Full Filing", content=text)]

    indices.append(("__END__", len(lines)))
    sections: list[Section] = []
    for (title, start), (_, end) in zip(indices, indices[1:], strict=False):
        body = "\n".join(lines[start + 1 : end]).strip()
        if not body:
            continue
        sections.append(Section(title=_sanitize_title(title), content=body))
    return sections or [Section(title="Full Filing", content=text)]


def _sanitize_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title)
    return title.strip().title()
