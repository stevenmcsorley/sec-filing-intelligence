"""State management for accession number deduplication."""

from __future__ import annotations

import asyncio
from typing import Protocol

from redis.asyncio import Redis


class AccessionStateStore(Protocol):
    """Protocol for deduplicating accession numbers across poll runs."""

    async def mark_seen(self, accession_number: str) -> bool:
        """Return True if accession_number was newly marked, False if already seen."""


class RedisAccessionStateStore:
    """Redis-backed store for accession deduplication."""

    def __init__(self, redis: Redis, key: str = "sec:ingestion:seen-accessions") -> None:
        self._redis = redis
        self._key = key

    async def mark_seen(self, accession_number: str) -> bool:
        added = await self._redis.sadd(self._key, accession_number)
        return added == 1


class InMemoryAccessionStateStore:
    """In-memory store used primarily for testing."""

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._lock = asyncio.Lock()

    async def mark_seen(self, accession_number: str) -> bool:
        async with self._lock:
            if accession_number in self._seen:
                return False
            self._seen.add(accession_number)
            return True
