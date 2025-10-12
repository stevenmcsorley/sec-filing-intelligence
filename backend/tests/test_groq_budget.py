from __future__ import annotations

import time

import pytest
from app.groq.budget import BudgetExceededError, TokenBudgetManager
from app.groq.metrics import (
    GROQ_BUDGET_EXHAUSTIONS_TOTAL,
    GROQ_BUDGET_REMAINING_TOKENS,
    GROQ_BUDGET_USAGE_TOKENS,
)


class FakePipeline:
    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis
        self._ops: list[tuple[str, tuple]] = []

    def incrby(self, key: str, amount: int) -> FakePipeline:
        self._ops.append(("incrby", (key, amount)))
        return self

    def ttl(self, key: str) -> FakePipeline:
        self._ops.append(("ttl", (key,)))
        return self

    async def execute(self) -> list[int]:
        results: list[int] = []
        for command, args in self._ops:
            if command == "incrby":
                results.append(await self._redis.incrby(*args))
            elif command == "ttl":
                results.append(await self._redis.ttl(*args))
        self._ops.clear()
        return results


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, int] = {}
        self._ttls: dict[str, int] = {}

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self)

    async def incrby(self, key: str, amount: int) -> int:
        self._store[key] = self._store.get(key, 0) + amount
        return self._store[key]

    async def decrby(self, key: str, amount: int) -> int:
        self._store[key] = self._store.get(key, 0) - amount
        return self._store[key]

    async def ttl(self, key: str) -> int:
        if key not in self._store:
            return -2
        expiry = self._ttls.get(key)
        if expiry is None:
            return -1
        remaining = expiry - int(time.time())
        return max(remaining, -1)

    async def expireat(self, key: str, epoch: int) -> bool:
        if key in self._store:
            self._ttls[key] = epoch
            return True
        return False

    async def get(self, key: str) -> int | None:
        return self._store.get(key)

    async def close(self) -> None:  # pragma: no cover - API parity
        return None


def _reset_metrics() -> None:
    GROQ_BUDGET_USAGE_TOKENS.clear()
    GROQ_BUDGET_REMAINING_TOKENS.clear()
    GROQ_BUDGET_EXHAUSTIONS_TOTAL.clear()


@pytest.mark.asyncio
async def test_reserve_and_commit_updates_metrics() -> None:
    _reset_metrics()
    redis = FakeRedis()
    manager = TokenBudgetManager(redis, prefix="test", cooldown_seconds=10)
    limiter = manager.limiter(service="summarizer", model="mixtral", daily_limit=100)
    assert limiter is not None

    reservation = await limiter.reserve(40)
    await reservation.commit(30)

    usage = GROQ_BUDGET_USAGE_TOKENS.labels("summarizer", "mixtral")._value.get()
    remaining = GROQ_BUDGET_REMAINING_TOKENS.labels("summarizer", "mixtral")._value.get()
    assert usage == 30
    assert remaining == 70


@pytest.mark.asyncio
async def test_budget_exhaustion_increments_counter() -> None:
    _reset_metrics()
    redis = FakeRedis()
    manager = TokenBudgetManager(redis, prefix="test", cooldown_seconds=10)
    limiter = manager.limiter(service="entity", model="llama", daily_limit=50)
    assert limiter is not None

    first = await limiter.reserve(40)
    await first.commit(40)

    with pytest.raises(BudgetExceededError):
        await limiter.reserve(20)

    exhaustions = GROQ_BUDGET_EXHAUSTIONS_TOTAL.labels("entity", "llama")._value.get()
    assert exhaustions == 1
