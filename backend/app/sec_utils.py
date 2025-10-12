"""Utilities for SEC EDGAR data processing."""

from __future__ import annotations

import re
from typing import NamedTuple


class IssuerInfo(NamedTuple):
    """Issuer information extracted from Form 4 filing."""
    cik: str
    name: str | None = None


def extract_issuer_cik(content: str) -> str | None:
    """Extract issuer CIK from filing content.

    Supports multiple filing types:
    - Form 4: <issuerCik> tags
    - Form 144, Schedule 13D/A: SUBJECT COMPANY -> CENTRAL INDEX KEY
    - Form 3: ISSUER section -> CENTRAL INDEX KEY

    Args:
        content: The raw content of the filing

    Returns:
        The issuer CIK as a string, or None if not found
    """
    # Try Form 4 XML format first
    issuer_cik_pattern = re.compile(r'<issuerCik>([^<]+)</issuerCik>', re.IGNORECASE)
    match = issuer_cik_pattern.search(content)
    if match:
        cik = match.group(1).strip()
        if cik.isdigit() and len(cik) <= 10:
            return cik

    # Try Form 144 / Schedule 13D/A header format
    # Look for CENTRAL INDEX KEY anywhere in the content
    cik_pattern = re.compile(r'CENTRAL INDEX KEY:\s*(\d+)', re.IGNORECASE)
    matches = cik_pattern.findall(content)
    if matches:
        # For Form 3, there are two CIKs - reporting owner and issuer
        # Take the second one (issuer) if there are multiple
        cik = matches[-1].strip()  # Last match is typically the issuer
        if cik.isdigit() and len(cik) <= 10:
            return cik

    return None


def extract_issuer_name(content: str) -> str | None:
    """Extract issuer name from filing content.

    Supports multiple filing types:
    - Form 4: <issuerName> tags
    - Form 144, Schedule 13D/A: SUBJECT COMPANY -> COMPANY CONFORMED NAME
    - Form 3: ISSUER section -> COMPANY CONFORMED NAME

    Args:
        content: The raw content of the filing

    Returns:
        The issuer name as a string, or None if not found
    """
    # Try Form 4 XML format first
    issuer_name_pattern = re.compile(r'<issuerName>([^<]+)</issuerName>', re.IGNORECASE)
    match = issuer_name_pattern.search(content)
    if match:
        return match.group(1).strip()

    # Try Form 144 / Schedule 13D/A header format
    # Look for COMPANY CONFORMED NAME anywhere in the content
    name_pattern = re.compile(r'COMPANY CONFORMED NAME:\s*([^\n\r]+)', re.IGNORECASE)
    matches = name_pattern.findall(content)
    if matches:
        # For Form 3, there are two names - reporting owner and issuer
        # Take the second one (issuer) if there are multiple
        name = matches[-1].strip()  # Last match is typically the issuer
        return name

    return None


def extract_issuer_info(content: str) -> IssuerInfo | None:
    """Extract issuer CIK and name from Form 4 filing XML content.

    Args:
        content: The raw XML content of the filing

    Returns:
        IssuerInfo with CIK and name, or None if CIK not found
    """
    cik = extract_issuer_cik(content)
    if not cik:
        return None

    name = extract_issuer_name(content)
    return IssuerInfo(cik=cik, name=name)