from __future__ import annotations

from pathlib import Path

import pytest
from app.ingestion.feed import EdgarFeedClient

FIXTURES = Path(__file__).parent / "fixtures" / "edgar"


@pytest.mark.parametrize(
    ("fixture_name", "expected_accession", "expected_cik", "expected_form"),
    [
        (
            "global_feed_sample.xml",
            "0001234567-25-000001",
            "1234567",
            "10-K",
        ),
        (
            "global_feed_sample.xml",
            "0000678900-25-000111",
            "67890",
            "8-K",
        ),
    ],
)
def test_parse_global_feed(
    fixture_name: str,
    expected_accession: str,
    expected_cik: str,
    expected_form: str,
) -> None:
    payload = (FIXTURES / fixture_name).read_text()
    client = EdgarFeedClient(base_headers={})
    entries = list(client._parse_feed(payload))  # type: ignore[attr-defined]
    accession_numbers = {entry.accession_number: entry for entry in entries}
    assert expected_accession in accession_numbers
    entry = accession_numbers[expected_accession]
    assert entry.cik.endswith(expected_cik)
    assert entry.form_type == expected_form
    assert entry.filing_href


def test_parse_company_feed() -> None:
    payload = (FIXTURES / "company_feed_sample.xml").read_text()
    client = EdgarFeedClient(base_headers={})
    entries = client.parse_company_feed(payload)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.accession_number == "0000123456-25-000210"
    assert entry.cik == "1234567"
    assert entry.form_type == "10-Q"
    assert entry.filing_href.endswith("0001234567-25-000210-index.htm")
